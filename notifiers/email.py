"""
notifiers/email.py

Gmail SMTP 발송 (Supabase shk/spk/suk/smp 키 사용).
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from notifiers._base import BaseNotifier
from scrapers._common import ConfigLoader


class EmailNotifier(BaseNotifier):
    channel_name = "email"
    
    def is_available(self) -> bool:
        ConfigLoader.load()
        return all([
            ConfigLoader.get_str("shk"),
            ConfigLoader.get_str("spk"),
            ConfigLoader.get_str("suk"),
            ConfigLoader.get_str("smp"),
        ])
    
    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        from_name: Optional[str] = None,
        is_html: bool = False,
        **kwargs,
    ) -> bool:
        ConfigLoader.load()
        
        host = ConfigLoader.get_str("shk")
        port_str = ConfigLoader.get_str("spk", "587")
        user = ConfigLoader.get_str("suk")
        password = ConfigLoader.get_str("smp")
        
        if not all([host, port_str, user, password]):
            print(f"[EmailNotifier] SMTP 설정 누락")
            return False
        
        try:
            port = int(port_str)
        except ValueError:
            print(f"[EmailNotifier] invalid port: {port_str}")
            return False
        
        try:
            msg = MIMEMultipart()
            msg["From"] = f"{from_name} <{user}>" if from_name else user
            msg["To"] = recipient
            msg["Subject"] = subject
            
            mime_type = "html" if is_html else "plain"
            msg.attach(MIMEText(body, mime_type, "utf-8"))
            
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls()
                server.login(user, password)
                server.send_message(msg)
            
            print(f"[EmailNotifier] sent to {recipient}")
            return True
        except Exception as e:
            print(f"[EmailNotifier] send failed: {e}")
            return False
