"""notifiers/kakao.py — KakaoTalk 채널 stub. 향후 구현 (Bizmessage 알림톡)."""
from __future__ import annotations
from notifiers._base import BaseNotifier


class KakaoNotifier(BaseNotifier):
    channel_name = "kakao"
    
    def is_available(self) -> bool:
        return False
    
    def send(self, recipient: str, subject: str, body: str, **kwargs) -> bool:
        print(f"[KakaoNotifier] not implemented yet (recipient={recipient})")
        return False
