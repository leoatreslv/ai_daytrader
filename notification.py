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
        self.chat_id = str(chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        self.set_bot_commands()

    def set_bot_commands(self):
        """Registers commands with Telegram Bot API for the menu."""
        if not self.token: return
        
        commands = [
            {"command": "status", "description": "Check connection & active symbol"},
            {"command": "symbol", "description": "Switch instrument (e.g. /symbol 1)"}
        ]
        try:
            response = requests.post(f"{self.base_url}/setMyCommands", json={"commands": commands}, timeout=5)
            if response.status_code == 200:
                logger.info("Telegram commands registered successfully.")
            else:
                logger.warning(f"Failed to register Telegram commands: {response.text}")
        except Exception as e:
            logger.error(f"Error registering Telegram commands: {e}")

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
            response = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=5)
            if response.status_code != 200:
                logger.error(f"Telegram send failed: {response.text}")
        except Exception as e:
            logger.error(f"Telegram connection error: {e}")

    def check_for_commands(self):
        """Polls for new commands from the authorized chat_id."""
        if not self.token or not self.chat_id:
            return []

        commands = []
        try:
            # timeout=0 for immediate return (we will control polling interval in main)
            url = f"{self.base_url}/getUpdates?offset={self.last_update_id + 1}&timeout=1"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    for result in data.get("result", []):
                        update_id = result.get("update_id")
                        self.last_update_id = max(self.last_update_id, update_id)
                        
                        message = result.get("message", {})
                        chat = message.get("chat", {})
                        text = message.get("text", "")
                        
                        # Security: Only accept commands from the configured chat_id
                        if str(chat.get("id")) == self.chat_id and text:
                            commands.append(text)
                            
        except Exception as e:
            logger.error(f"Telegram polling error: {e}")
            
        return commands

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

    def check_commands(self):
        """Collect commands from all providers."""
        all_cmds = []
        for p in self.providers:
            if hasattr(p, 'check_for_commands'):
                all_cmds.extend(p.check_for_commands())
        return all_cmds
