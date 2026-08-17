"""
WebFetch로 가져온 뉴스 항목(JSON)을 관련성 필터 + 중복제거 파이프라인에 투입한다.

로컬 실행(collect.py)은 feedparser로 직접 RSS를 가져오지만, Claude Code
클라우드 routine 샌드박스는 정책상 임의 외부 도메인에 대한 raw 소켓 접근을
차단한다 (WebFetch 도구를 통한 접근만 허용). 이 경우 각 소스를 WebFetch로
가져온 뒤 추출된 항목 목록을 이 스크립트에 stdin JSON으로 넘겨, collect.py와
동일한 필터/중복제거/저장 로직을 거치게 한다.

입력 (stdin): JSON 배열, 각 원소는
    {"title": str, "url": str, "published": str(선택), "summary": str(선택)}

사용법:
    python src/ingest_items.py --source "CoinDesk" --category media --lang en --filter true < items.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from collect import DATA_DIR, build_keyword_matcher, load_yaml
from store import SeenStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--category", required=True, choices=["media", "regulators", "google_alerts", "company_blogs"])
    parser.add_argument("--lang", default="en")
    parser.add_argument("--filter", default="true", choices=["true", "false"])
    args = parser.parse_args()

    raw = sys.stdin.read().strip()
    try:
        entries = json.loads(raw) if raw else []
    except json.JSONDecodeError as e:  # noqa: BLE001
        print(f"[error] {args.source}: JSON 파싱 실패 ({e})", file=sys.stderr)
        sys.exit(1)

    keywords_cfg = load_yaml("keywords.yaml")
    is_relevant = build_keyword_matcher(keywords_cfg)
    apply_filter = args.filter == "true"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = DATA_DIR / f"digest_{today}.json"

    if out_path.exists():
        digest = json.loads(out_path.read_text(encoding="utf-8"))
    else:
        digest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "count": 0, "items": []}

    now_iso = datetime.now(timezone.utc).isoformat()
    added = 0
    with SeenStore() as store:
        for e in entries:
            url = (e.get("url") or "").strip()
            title = (e.get("title") or "").strip()
            if not url or not title:
                continue
            if not store.is_new(url):
                continue
            summary = (e.get("summary") or "")[:600]
            if apply_filter and not is_relevant(title, summary):
                continue
            digest["items"].append(
                {
                    "category": args.category,
                    "source": args.source,
                    "lang": args.lang,
                    "title": title,
                    "url": url,
                    "published": e.get("published", ""),
                    "summary": summary,
                }
            )
            store.mark_seen(url, args.source, title, now_iso)
            added += 1

    digest["count"] = len(digest["items"])
    out_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {args.source}: 신규 {added}건 추가 (누적 {digest['count']}건) -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
