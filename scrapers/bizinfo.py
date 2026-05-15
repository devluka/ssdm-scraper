"""
scrapers/bizinfo.py

Bizinfo (기업마당) API 호출 + opportunities_raw INSERT.

- Endpoint: https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do
- Auth: crtfcKey 파라미터 (Supabase의 'bzk' 키)
- Response: { "jsonArray": [...] }
- 8개 카테고리(01~07, 09) 전체 페이지네이션

GitHub Actions에서 한국에 가까운 IP로 호출 (해외 IP 차단 우회).
"""
from __future__ import annotations

import math
import sys
import time
from typing import Any, Dict, List, Tuple

import requests

from scrapers._common import (
    ConfigLoader,
    DEFAULT_HEADERS,
    insert_raw,
    trigger_collector,
)


_BASE_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
_PAGE_SIZE = 100
_CATEGORIES = ["01", "02", "03", "04", "05", "06", "07", "09"]


def _fetch_page(api_key: str, page: int, category: str) -> Tuple[List[Dict[str, Any]], int]:
    """단일 페이지 fetch. (items, totCnt) 반환."""
    params = {
        "crtfcKey": api_key,
        "dataType": "json",
        "pageUnit": _PAGE_SIZE,
        "pageIndex": page,
        "searchLclasId": category,
    }
    resp = requests.get(_BASE_URL, params=params, headers=DEFAULT_HEADERS, timeout=20)
    resp.raise_for_status()
    
    try:
        data = resp.json()
    except ValueError as exc:
        body_preview = resp.text[:500].replace("\n", " ")
        print(f"[Bizinfo] invalid JSON cat={category} page={page}: {exc}")
        print(f"[Bizinfo] body preview: {body_preview}")
        raise
    
    items = data.get("jsonArray") if isinstance(data, dict) else None
    if not isinstance(items, list):
        body_preview = resp.text[:500].replace("\n", " ")
        print(f"[Bizinfo] missing jsonArray cat={category} page={page}")
        print(f"[Bizinfo] body preview: {body_preview}")
        raise ValueError("Bizinfo response missing jsonArray")
    
    total = int(items[0].get("totCnt", 0)) if items else 0
    return items, total


def _fetch_category(api_key: str, category: str) -> List[Dict[str, Any]]:
    """단일 카테고리 전체 페이지 fetch."""
    items, total = _fetch_page(api_key, page=1, category=category)
    if not total:
        return items
    total_pages = math.ceil(total / _PAGE_SIZE)
    print(f"[Bizinfo] cat={category} total={total} pages={total_pages}")
    
    all_items = list(items)
    for page in range(2, total_pages + 1):
        page_items, _ = _fetch_page(api_key, page=page, category=category)
        all_items.extend(page_items)
        time.sleep(0.2)  # 매너 있는 호출 간격
    return all_items


def fetch_all() -> List[Dict[str, Any]]:
    """전체 카테고리 수집 + pblancId 기준 dedup."""
    api_key = ConfigLoader.get_str("bzk")
    print(f"[Bizinfo] API key length: {len(api_key)}")
    if not api_key:
        print("[Bizinfo] No API key — Supabase bzk 키 확인")
        return []
    
    all_items: List[Dict[str, Any]] = []
    seen_ids: set = set()
    
    try:
        for cat in _CATEGORIES:
            items = _fetch_category(api_key, cat)
            for item in items:
                pid = item.get("pblancId")
                if pid and pid in seen_ids:
                    continue
                if pid:
                    seen_ids.add(pid)
                # ext_id 필드 표준화 (insert_raw가 사용)
                item["ext_id"] = pid
                all_items.append(item)
        print(f"[Bizinfo] total fetched (dedup): {len(all_items)}")
        return all_items
    except Exception as e:
        print(f"[Bizinfo] fetch error: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    started_at = time.time()
    print(f"[Bizinfo Scrap] start")
    
    # 1. ConfigLoader 로드 (Supabase에서 모든 키)
    ConfigLoader.load()
    
    # 2. Bizinfo fetch
    items = fetch_all()
    if not items:
        print("[Bizinfo Scrap] no items, exit")
        return 1
    
    # 3. opportunities_raw에 INSERT
    result = insert_raw(source_key="bizinfo", items=items, ext_id_field="ext_id")
    print(f"[Bizinfo Scrap] insert result: {result}")
    
    # 4. sdm-collector trigger
    trigger_collector(source_key="bizinfo")
    
    elapsed = round(time.time() - started_at, 2)
    print(f"[Bizinfo Scrap] done ({elapsed}s)")
    return 0 if result["inserted"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
