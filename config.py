# config.py - простой конфиг без проверок
import os

# Токен бота - берем из переменных окружения или используем дефолтный
API_TOKEN = os.environ.get('API_TOKEN', '8409938113:AAHjLQcO9WtqKqL8vYpM6vzq6Z5wXqoX6oE')

# Простое логирование
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if API_TOKEN:
    logger.info(f"✅ Токен загружен (первые 10 символов): {API_TOKEN[:10]}...")
else:
    logger.error("❌ API_TOKEN не найден")
