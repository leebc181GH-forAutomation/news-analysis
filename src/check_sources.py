"""
config/sources.yaml에 등록된 모든 피드 URL의 유효성을 점검한다.
url이 비어있는 항목(unverified)은 건너뛰고 목록만 알려준다.

사용법:
    python src/check_sources.py
"""

from pathlib import Path

import feedparser
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def main():
    with open(CONFIG_DIR / "sources.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    ok, broken, empty = 0, 0, 0

    for category in ("media", "regulators", "google_alerts"):
        print(f"\n== {category} ==")
        for src in cfg.get(category, []) or []:
            name = src.get("name", "?")
            url = (src.get("url") or "").strip()
            if not url:
                print(f"  [빈 URL] {name} - {src.get('note', 'url 미설정')}")
                empty += 1
                continue
            parsed = feedparser.parse(url)
            if parsed.entries:
                print(f"  [OK] {name} - entries={len(parsed.entries)}")
                ok += 1
            else:
                print(f"  [실패] {name} - {url}")
                broken += 1

    print(f"\n요약: 정상 {ok} / 실패 {broken} / 미설정 {empty}")


if __name__ == "__main__":
    main()
