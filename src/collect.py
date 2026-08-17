"""
RWA / Digital Asset / Tokenized Securities&Fund / Stablecoin / On-chain Finance
일일 뉴스 수집 스크립트.

config/sources.yaml 에 정의된 RSS/Atom 피드(매체, 규제기구, Google Alerts)를
모두 수집하고, config/keywords.yaml 기준으로 관련성 필터링한 뒤,
data/seen.sqlite3 에 없는(=오늘 새로 발견된) 기사만 골라
data/digest_<YYYYMMDD>.json 으로 저장한다.

이 스크립트는 LLM을 호출하지 않는다. 요약/시사점 추출은 이 JSON을 읽는
Claude Code 예약 에이전트(AGENT_PROMPT.md)가 수행한다.

사용법:
    python src/collect.py            # 수집 + seen 마킹 + JSON 저장
    python src/collect.py --dry-run  # 수집만 하고 seen 마킹은 하지 않음(테스트용)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import yaml

from store import SeenStore

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def flatten_sources(sources_cfg: dict):
    """category별로 묶인 sources.yaml을 (category, source_dict) 튜플 리스트로 변환."""
    flat = []
    for category in ("media", "regulators", "google_alerts"):
        for src in sources_cfg.get(category, []) or []:
            flat.append((category, src))
    return flat


def build_keyword_matcher(keywords_cfg: dict):
    include = []
    for lang_list in keywords_cfg.get("include", {}).values():
        include.extend(k.lower() for k in lang_list)
    exclude = []
    for lang_list in keywords_cfg.get("exclude", {}).values():
        exclude.extend(k.lower() for k in lang_list)

    def is_relevant(title: str, summary: str) -> bool:
        text = f"{title} {summary}".lower()
        if any(bad in text for bad in exclude):
            return False
        return any(good in text for good in include)

    return is_relevant


def clean_summary(entry) -> str:
    raw = entry.get("summary", "") or entry.get("description", "")
    # 아주 단순한 HTML 태그 제거 (의존성 추가를 피하기 위해 정규식 대신 최소 처리)
    import re

    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:600]


def collect_source(category: str, src: dict, is_relevant, store: SeenStore, dry_run: bool):
    url = (src.get("url") or "").strip()
    name = src.get("name", url)
    if not url:
        return [], f"[skip] {name}: url 미설정"

    apply_filter = src.get("filter", True)

    try:
        parsed = feedparser.parse(url)
    except Exception as e:  # noqa: BLE001
        return [], f"[error] {name}: fetch 실패 ({e})"

    if getattr(parsed, "bozo", False) and not parsed.entries:
        return [], f"[error] {name}: 파싱 실패 또는 빈 피드 ({getattr(parsed, 'bozo_exception', '')})"

    now_iso = datetime.now(timezone.utc).isoformat()
    new_items = []
    for entry in parsed.entries:
        link = entry.get("link", "").strip()
        title = entry.get("title", "").strip()
        if not link or not title:
            continue
        if not store.is_new(link):
            continue

        summary = clean_summary(entry)

        if apply_filter and not is_relevant(title, summary):
            continue

        published = entry.get("published", "") or entry.get("updated", "")

        new_items.append(
            {
                "category": category,
                "source": name,
                "lang": src.get("lang", "en"),
                "title": title,
                "url": link,
                "published": published,
                "summary": summary,
            }
        )

        if not dry_run:
            store.mark_seen(link, name, title, now_iso)

    return new_items, f"[ok] {name}: 신규 {len(new_items)}건"


def collect_all(dry_run: bool = False):
    sources_cfg = load_yaml("sources.yaml")
    keywords_cfg = load_yaml("keywords.yaml")
    is_relevant = build_keyword_matcher(keywords_cfg)

    all_items = []
    logs = []

    with SeenStore() as store:
        for category, src in flatten_sources(sources_cfg):
            items, log = collect_source(category, src, is_relevant, store, dry_run)
            all_items.extend(items)
            logs.append(log)

    return all_items, logs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="seen.sqlite3에 기록하지 않고 수집 결과만 확인 (테스트용)",
    )
    args = parser.parse_args()

    items, logs = collect_all(dry_run=args.dry_run)

    for log in logs:
        print(log, file=sys.stderr)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = DATA_DIR / f"digest_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "count": len(items),
                "items": items,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n총 {len(items)}건의 신규 기사를 {out_path} 에 저장했습니다.", file=sys.stderr)
    print(str(out_path))


if __name__ == "__main__":
    main()
