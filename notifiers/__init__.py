"""
notifiers — 멀티 알림 허브.

채널 추가 방식:
1. notifiers/{채널}.py 파일 생성 (BaseNotifier 상속)
2. NOTIFIER_REGISTRY에 등록
"""
from notifiers.email import EmailNotifier
from notifiers.sms import SMSNotifier
from notifiers.kakao import KakaoNotifier
from notifiers.slack import SlackNotifier
from notifiers.desktop import DesktopNotifier
from notifiers.webhook import WebhookNotifier


NOTIFIER_REGISTRY = {
    "email": EmailNotifier(),
    "sms": SMSNotifier(),
    "kakao": KakaoNotifier(),
    "slack": SlackNotifier(),
    "desktop": DesktopNotifier(),
    "webhook": WebhookNotifier(),
}


def get_notifier(channel: str):
    """채널명으로 notifier 인스턴스 조회."""
    return NOTIFIER_REGISTRY.get(channel)


def list_available_channels() -> list[str]:
    """is_available()=True인 채널만 리스트."""
    return [
        ch for ch, notifier in NOTIFIER_REGISTRY.items()
        if notifier.is_available()
    ]


__all__ = ["NOTIFIER_REGISTRY", "get_notifier", "list_available_channels"]
