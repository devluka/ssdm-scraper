"""
scripts/update_dashboard.py

Supabase scrap_monitor 뷰 → docs/data.json 갱신.

GitHub Actions의 update-dashboard.yml이 KST 06:00, 16:30에 실행.
별도 cron으로 돌아서 scrap·collect 둘 다 끝난 시점의 최종 상태 캡처.

워크플로 다음 step에서 git commit + push → GitHub Pages 자동 갱신.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

from scrapers._common import get_supabase


_KST = timezone(timedelta(hours=9))
_OUTPUT_PATH = Path(__file__).parent.parent / "docs" / "data.json"


def _fetch_scrap_monitor() -> List[Dict[str, Any]]:
    """scrap_monitor 뷰 SELECT."""
    try:
        sb = get_supabase()
        res = sb.table("scrap_monitor").select("*").execute()
        return res.data or []
    except Exception as e:
        print(f"[dashboard] scrap_monitor failed: {e}")
        return []


def _fetch_recent_errors(limit: int = 10) -> List[Dict[str, Any]]:
    """최근 에러 N건."""
    try:
        sb = get_supabase()
        res = (
            sb.table("opportunities_raw")
            .select("source_key, fetched_at, error_message, ext_id")
            .eq("process_status", "error")
            .order("fetched_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[dashboard] recent_errors failed: {e}")
        return []


def _fetch_7day_trend() -> List[Dict[str, Any]]:
    """최근 7일 일별 수집 추이."""
    try:
        sb = get_supabase()
        # date_trunc 못 쓰니까 raw 데이터에서 Python으로 집계
        seven_days_ago = (datetime.now(_KST) - timedelta(days=7)).isoformat()
        res = (
            sb.table("opportunities_raw")
            .select("source_key, fetched_at")
            .gte("fetched_at", seven_days_ago)
            .execute()
        )
        rows = res.data or []
        
        # source_key + 날짜별 카운트
        counts: Dict[str, Dict[str, int]] = {}
        for row in rows:
            src = row["source_key"]
            fetched = row.get("fetched_at", "")
            day = fetched[:10] if len(fetched) >= 10 else "?"
            counts.setdefault(src, {})
            counts[src][day] = counts[src].get(day, 0) + 1
        
        # 결과 형식
        trend = []
        for src, day_counts in counts.items():
            for day, cnt in sorted(day_counts.items()):
                trend.append({"source_key": src, "date": day, "count": cnt})
        return trend
    except Exception as e:
        print(f"[dashboard] 7day_trend failed: {e}")
        return []


def main():
    print(f"[dashboard] start")
    
    sources = _fetch_scrap_monitor()
    errors = _fetch_recent_errors(limit=10)
    trend = _fetch_7day_trend()
    
    payload = {
        "generated_at": datetime.now(_KST).isoformat(),
        "sources": sources,
        "recent_errors": errors,
        "trend_7d": trend,
    }
    
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"[dashboard] wrote {_OUTPUT_PATH}")
    print(f"  sources: {len(sources)}")
    print(f"  errors: {len(errors)}")
    print(f"  trend points: {len(trend)}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
