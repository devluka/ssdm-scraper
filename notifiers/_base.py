"""
notifiers/_base.py

알림 채널 추상 인터페이스.

향후 채널 추가 시 BaseNotifier 상속 + send() 구현.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class BaseNotifier(ABC):
    """모든 알림 채널의 공통 인터페이스."""
    
    channel_name: str = ""
    
    @abstractmethod
    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        **kwargs,
    ) -> bool:
        """
        알림 발송.
        
        Args:
            recipient: 받는 사람 (이메일 주소, 전화번호, Slack 채널 등)
            subject: 제목
            body: 본문
            **kwargs: 채널별 추가 옵션
        
        Returns:
            성공 시 True, 실패 시 False
        """
        ...
    
    def is_available(self) -> bool:
        """채널 사용 가능 여부 (키·설정 확인)."""
        return True
