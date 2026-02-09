from abc import ABC, abstractmethod
import requests
from logger import setup_logger

logger = setup_logger("Notifier")

class NotificationProvider(ABC):
    """Abstract base class for notification providers."""
    @abstractmethod
    def send_message(self, message: str):
        pass

class TelegramProvider(NotificationProvider):
    """Sends notifications via Telegram Bot API."""
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_message(self, message: str):
        if not self.token or not self.chat_id:
            logger.warning("Telegram token or chat_id not set. Cannot send notification.")
            return

        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            response = requests.post(self.base_url, json=payload, timeout=5)
            if response.status_code != 200:
                logger.error(f"Telegram send failed: {response.text}")
        except Exception as e:
            logger.error(f"Telegram connection error: {e}")

class NotificationManager:
    """Manages multiple notification providers."""
    def __init__(self):
        self.providers = []
    
    def add_provider(self, provider: NotificationProvider):
        self.providers.append(provider)
        
    def notify(self, message: str):
        """Send message to all registered providers."""
        for p in self.providers:
            p.send_message(message)
