"""notifiers/webhook.py — 커스텀 웹훅 채널 stub. 향후 구현."""
from __future__ import annotations
from notifiers._base import BaseNotifier


class WebhookNotifier(BaseNotifier):
    channel_name = "webhook"
    
    def is_available(self) -> bool:
        return False
    
    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        print(f"[WebhookNotifier] not implemented yet (recipient={recipient})")
        return False
