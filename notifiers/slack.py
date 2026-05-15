"""notifiers/slack.py — Slack incoming webhook stub. 향후 구현."""
from __future__ import annotations
from notifiers._base import BaseNotifier


class SlackNotifier(BaseNotifier):
    channel_name = "slack"
    
    def is_available(self) -> bool:
        return False
    
    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        print(f"[SlackNotifier] not implemented yet (recipient={recipient})")
        return False
