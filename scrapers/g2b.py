"""
scrapers/g2b.py

G2B (나라장터) 입찰공고 API 호출 + opportunities_raw INSERT.

- Endpoint: https://apis.data.go.kr/1230000/ao/PubDataOpnStdService
- Operation: /getDataSetOpnStdBidPblancInfo (입찰공고)
- Auth: ServiceKey 쿼리 파라미터 (Supabase의 'gtd' Decoding 키)
- Response: { "response": { "header": {...}, "body": { "items": [...] } } }
- 입찰공고일시 범위 1개월 제한 → 어제~오늘 슬라이싱

추가 가능한 endpoint (현재 비활성):
- /getDataSetOpnStdScsbidInfo (낙찰정보)
- /getDataSetOpnStdCntrctInfo (계약정보)
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from scrapers._common import (
    ConfigLoader,
    DEFAULT_HEADERS,
    insert_raw,
    trigger_collector,
)


_BASE_URL = "https://apis.data.go.kr/1230000/ao/PubDataOpnStdService"
_OPERATION = "/getDataSetOpnStdBidPblancInfo"
_PAGE_SIZE = 100
_KST = timezone(timedelta(hours=9))


def _kst_range(hours: int = 24) -> tuple[str, str]:
    """
    검색 범위 계산.
    G2B는 'YYYYMMDDHHMM' 형식, 1개월 이내.
    기본은 최근 24시간 (cron이 KST 05:00 / 15:30 두 번 도니까 충분히 커버).
    """
    now = datetime.now(_KST)
    bgn = now - timedelta(hours=hours)
    return (
        bgn.strftime("%Y%m%d%H%M"),
        now.strftime("%Y%m%d%H%M"),
    )


def _fetch_page(
    service_key: str,
    page: int,
    bgn_dt: str,
    end_dt: str,
) -> tuple[List[Dict[str, Any]], int]:
    """단일 페이지 fetch. (items, totalCount)."""
    params = {
        "ServiceKey": service_key,
        "type": "json",
        "numOfRows": _PAGE_SIZE,
        "pageNo": page,
        "bidNtceBgnDt": bgn_dt,
        "bidNtceEndDt": end_dt,
    }
    resp = requests.get(
        _BASE_URL + _OPERATION,
        params=params,
        headers=DEFAULT_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    
    try:
        data = resp.json()
    except ValueError as exc:
        body_preview = resp.text[:500].replace("\n", " ")
        print(f"[G2B] invalid JSON page={page}: {exc}")
        print(f"[G2B] body preview: {body_preview}")
        raise
    
    # 응답 구조: response.body.items 또는 response.header
    response = data.get("response", {}) if isinstance(data, dict) else {}
    header = response.get("header", {})
    body = response.get("body", {})
    
    # 헤더 결과코드 검증
    result_code = header.get("resultCode", "")
    if result_code and result_code not in ("00", "0"):
        result_msg = header.get("resultMsg", "")
        print(f"[G2B] API error: code={result_code} msg={result_msg}")
        return [], 0
    
    items = body.get("items", [])
    if isinstance(items, dict):
        # 일부 정부 API는 단일 결과 시 dict로 반환
        items = [items.get("item")] if items.get("item") else []
    if not isinstance(items, list):
        items = []
    
    # totalCount는 응답에 있음
    total = int(body.get("totalCount", len(items)))
    return items, total


def fetch_all(hours: int = 24) -> List[Dict[str, Any]]:
    """최근 N시간의 입찰공고 전체 페이지네이션."""
    service_key = ConfigLoader.get_str("gtd")
    print(f"[G2B] ServiceKey length: {len(service_key)}")
    if not service_key:
        print("[G2B] No ServiceKey — Supabase gtd 키 확인")
        return []
    
    bgn_dt, end_dt = _kst_range(hours=hours)
    print(f"[G2B] range {bgn_dt} ~ {end_dt} (KST)")
    
    all_items: List[Dict[str, Any]] = []
    seen_ids: set = set()
    
    try:
        # 첫 페이지로 totalCount 파악
        first_items, total = _fetch_page(service_key, page=1, bgn_dt=bgn_dt, end_dt=end_dt)
        if not total:
            print(f"[G2B] no items in range")
            return []
        
        total_pages = (total + _PAGE_SIZE - 1) // _PAGE_SIZE
        print(f"[G2B] total={total} pages={total_pages}")
        
        # ext_id 표준화 (bidNtceNo + bidNtceOrd)
        for item in first_items:
            bid_no = item.get("bidNtceNo")
            bid_ord = item.get("bidNtceOrd", "000")
            if not bid_no:
                continue
            ext_id = f"{bid_no}-{bid_ord}"
            if ext_id in seen_ids:
                continue
            seen_ids.add(ext_id)
            item["ext_id"] = ext_id
            all_items.append(item)
        
        # 나머지 페이지
        for page in range(2, total_pages + 1):
            page_items, _ = _fetch_page(service_key, page=page, bgn_dt=bgn_dt, end_dt=end_dt)
            for item in page_items:
                bid_no = item.get("bidNtceNo")
                bid_ord = item.get("bidNtceOrd", "000")
                if not bid_no:
                    continue
                ext_id = f"{bid_no}-{bid_ord}"
                if ext_id in seen_ids:
                    continue
                seen_ids.add(ext_id)
                item["ext_id"] = ext_id
                all_items.append(item)
            time.sleep(0.3)  # G2B는 30 tps 제한
        
        print(f"[G2B] total fetched (dedup): {len(all_items)}")
        return all_items
    except Exception as e:
        print(f"[G2B] fetch error: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    started_at = time.time()
    print(f"[G2B Scrap] start")
    
    # 1. ConfigLoader
    ConfigLoader.load()
    
    # 2. G2B fetch (최근 24시간)
    items = fetch_all(hours=24)
    if not items:
        print("[G2B Scrap] no items, exit")
        return 1
    
    # 3. opportunities_raw INSERT
    result = insert_raw(source_key="g2b", items=items, ext_id_field="ext_id")
    print(f"[G2B Scrap] insert result: {result}")
    
    # 4. sdm-collector trigger
    trigger_collector(source_key="g2b")
    
    elapsed = round(time.time() - started_at, 2)
    print(f"[G2B Scrap] done ({elapsed}s)")
    return 0 if result["inserted"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
