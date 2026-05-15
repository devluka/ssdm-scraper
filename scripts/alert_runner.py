"""
scripts/alert_runner.py

멀티 알림 허브 진입점.

GitHub Actions의 alert.yml workflow_dispatch가 호출.
input으로 채널 리스트 + 알림 타입 받아서 적절한 notifier로 발송.

사용 예 (수동):
    ALERT_TYPE=deadline_imminent CHANNELS=email RECIPIENTS=user@example.com \\
        python scripts/alert_runner.py

향후 cron 추가 시 input 자동 채워짐.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from typing import Any, Dict, List

from notifiers import get_notifier, list_available_channels
from scrapers._common import ConfigLoader, get_supabase


def _fetch_deadline_imminent(days: int = 7) -> List[Dict[str, Any]]:
    """마감 N일 이내 공고 조회."""
    sb = get_supabase()
    today = date.today()
    deadline_max = today + timedelta(days=days)
    
    try:
        res = (
            sb.table("opportunities")
            .select("id, source_key, title, organization, deadline, url")
            .gte("deadline", today.isoformat())
            .lte("deadline", deadline_max.isoformat())
            .order("deadline")
            .limit(50)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[alert] fetch deadline_imminent failed: {e}")
        return []


def _build_email_body(opps: List[Dict[str, Any]]) -> tuple[str, str]:
    """이메일 본문 생성 (subject, body)."""
    today = date.today()
    if not opps:
        return (
            f"[ẞDM] 마감 임박 공고 없음 ({today.isoformat()})",
            "오늘 알림 대상 공고가 없습니다."
        )
    
    subject = f"[ẞDM] 마감 임박 공고 {len(opps)}건 ({today.isoformat()})"
    
    lines = [f"마감 임박 공고 {len(opps)}건입니다.\n"]
    for i, opp in enumerate(opps, 1):
        deadline = opp.get("deadline", "?")
        title = opp.get("title", "?")
        org = opp.get("organization", "?")
        url = opp.get("url", "")
        source = opp.get("source_key", "?")
        
        lines.append(f"{i}. [{source}] {title}")
        lines.append(f"   기관: {org}")
        lines.append(f"   마감: {deadline}")
        if url:
            lines.append(f"   링크: {url}")
        lines.append("")
    
    return subject, "\n".join(lines)


def main():
    started_at = time.time()
    
    # 입력 파라미터 (env 또는 GitHub Actions inputs)
    alert_type = os.environ.get("ALERT_TYPE", "deadline_imminent").strip()
    channels_str = os.environ.get("CHANNELS", "email").strip()
    recipients_str = os.environ.get("RECIPIENTS", "").strip()
    
    if not recipients_str:
        # 폴백: Supabase의 SMTP user 자기 자신에게
        ConfigLoader.load()
        recipients_str = ConfigLoader.get_str("suk")
    
    channels = [c.strip() for c in channels_str.split(",") if c.strip()]
    recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]
    
    print(f"[alert] type={alert_type}, channels={channels}, recipients={recipients}")
    
    if not recipients:
        print("[alert] no recipients, exit")
        return 1
    
    # 데이터 조회
    if alert_type == "deadline_imminent":
        opps = _fetch_deadline_imminent(days=7)
    else:
        print(f"[alert] unknown alert_type: {alert_type}")
        return 1
    
    # 본문 생성
    subject, body = _build_email_body(opps)
    print(f"[alert] subject: {subject}")
    print(f"[alert] body length: {len(body)} chars")
    
    # 채널별 발송
    success_channels = []
    failed_channels = []
    
    for channel in channels:
        notifier = get_notifier(channel)
        if not notifier:
            print(f"[alert] unknown channel: {channel}")
            failed_channels.append(channel)
            continue
        
        if not notifier.is_available():
            print(f"[alert] channel '{channel}' not available (config 누락 또는 미구현)")
            failed_channels.append(channel)
            continue
        
        for recipient in recipients:
            ok = notifier.send(
                recipient=recipient,
                subject=subject,
                body=body,
                from_name="ẞDM Alert",
            )
            if ok:
                success_channels.append(f"{channel}→{recipient}")
            else:
                failed_channels.append(f"{channel}→{recipient}")
    
    elapsed = round(time.time() - started_at, 2)
    print(f"\n[alert] === Summary ({elapsed}s) ===")
    print(f"  available channels: {list_available_channels()}")
    print(f"  success: {success_channels}")
    print(f"  failed:  {failed_channels}")
    
    return 0 if success_channels else 1


if __name__ == "__main__":
    sys.exit(main())
