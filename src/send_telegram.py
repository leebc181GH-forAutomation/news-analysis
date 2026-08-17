"""
텍스트 파일을 Telegram Bot API로 전송한다 (표준 라이브러리만 사용, 추가 의존성 없음).

Claude Code 예약 에이전트가 요약/시사점 다이제스트를 작성한 뒤 이 스크립트를
호출해 실제 발송을 수행한다. 4096자 제한을 넘으면 문단 단위로 자동 분할한다.

사용법:
    python src/send_telegram.py data/digest_send_20260817.txt
    cat message.txt | python src/send_telegram.py -

환경변수 (.env 또는 실제 환경변수):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID

메시지는 Telegram parse_mode=HTML로 전송된다. 허용 태그: <b> <i> <u> <s>
<a href="..."> <code> <pre>. 그 외 태그(예: <ul>, <br>)는 지원되지 않으므로
줄바꿈은 개행 문자로, 목록은 "- " 접두사로 표현할 것.
"""

import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_LEN = 4000  # Telegram 한도(4096)보다 여유를 둠


def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def split_chunks(text: str, max_len: int = MAX_LEN):
    chunks = []
    while len(text) > max_len:
        cut = text.rfind("\n\n", 0, max_len)
        if cut == -1:
            cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        chunks.append(text)
    return chunks


def send_message(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8")


def main():
    if len(sys.argv) != 2:
        print("usage: python src/send_telegram.py <text_file|->", file=sys.stderr)
        sys.exit(1)

    load_dotenv(ROOT / ".env")

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 설정되어 있지 않습니다. "
            ".env 파일을 확인하세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    src = sys.argv[1]
    text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    text = text.strip()
    if not text:
        print("전송할 내용이 비어 있습니다.", file=sys.stderr)
        sys.exit(1)

    chunks = split_chunks(text)
    for i, chunk in enumerate(chunks, 1):
        try:
            status, body = send_message(token, chat_id, chunk)
            print(f"[{i}/{len(chunks)}] status={status}", file=sys.stderr)
        except urllib.error.HTTPError as e:  # noqa: BLE001
            print(f"[{i}/{len(chunks)}] HTTP 오류: {e.code} {e.read().decode('utf-8')}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(chunks)}] 전송 실패: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"총 {len(chunks)}개 메시지 발송 완료.", file=sys.stderr)


if __name__ == "__main__":
    main()
