"""notifiers/sms.py — SMS 채널 stub. 향후 구현 (NHN Toast, AWS SNS 등)."""
from __future__ import annotations
from notifiers._base import BaseNotifier


class SMSNotifier(BaseNotifier):
    channel_name = "sms"
    
    def is_available(self) -> bool:
        return False
    
    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        print(f"[SMSNotifier] not implemented yet (recipient={recipient})")
        return False
