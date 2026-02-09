import config
import time
import logging
import sys
from notification import NotificationManager, TelegramProvider

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("TestTelegram")

def test_polling():
    logger.info("--- Testing Telegram Polling ---")
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials missing in .env")
        return

    notifier = NotificationManager()
    provider = TelegramProvider(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    notifier.add_provider(provider)
    
    logger.info("Waiting for commands... (Type /status in Telegram)")
    
    # Run loop for 20 seconds
    end_time = time.time() + 20
    while time.time() < end_time:
        try:
            logger.info("Checking updates...")
            cmds = notifier.check_commands()
            if cmds:
                for cmd in cmds:
                    logger.info(f"RECEIVED COMMAND: {cmd}")
                    provider.send_message(f"✅ Ack: {cmd}")
            else:
                logger.info("No commands.")
        except Exception as e:
            logger.error(f"Error: {e}")
            
        time.sleep(2)

if __name__ == "__main__":
    test_polling()
