# config.py - файл конфигурации Telegram бота
import os

# ==================== ОСНОВНЫЕ НАСТРОЙКИ ====================
API_TOKEN = os.environ.get('API_TOKEN', '8409938113:AAHjLQcO9WtqKqL8vYpM6vzq6Z5wXqoX6oE')

# ==================== ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ ====================
MAX_RETRIES = 3                     # Максимум попыток переподключения
RETRY_DELAY = 5                    # Задержка между попытками (секунды)
POLLING_TIMEOUT = 30               # Таймаут polling (секунды)
REQUEST_TIMEOUT = 10               # Таймаут HTTP запросов (секунды)
MAX_MESSAGE_LENGTH = 4096          # Максимальная длина сообщения Telegram

# ==================== НАСТРОЙКИ БАЗЫ ДАННЫХ ====================
USER_DATA_FILE = 'user_data.json'  # Файл для хранения данных пользователей
AUTO_SAVE_INTERVAL = 300           # Интервал автосохранения (секунд)

# ==================== НАСТРОЙКИ ВЕБ-СЕРВЕРА ====================
WEB_SERVER_PORT = int(os.environ.get('PORT', 10000))  # Порт веб-сервера
WEB_SERVER_HOST = '0.0.0.0'                           # Хост веб-сервера
WEB_SERVER_THREADS = 4                                # Количество потоков веб-сервера

# ==================== НАСТРОЙКИ САМОПИНГА ====================
SELF_PING_URL = f"https://{os.environ.get('RENDER_SERVICE_NAME', 'rus-comma-bot')}.onrender.com"
SELF_PING_INTERVAL = 300                              # Интервал самопинга (секунд)

# ==================== ПРОВЕРКА НАСТРОЕК ====================
# Проверяем, что токен установлен
if not API_TOKEN:
    raise ValueError("❌ ОШИБКА: API_TOKEN не найден! Установите переменную окружения API_TOKEN на Render")

# Проверяем формат токена (должен содержать двоеточие)
if ':' not in API_TOKEN:
    raise ValueError(f"❌ ОШИБКА: Неверный формат API_TOKEN: {API_TOKEN}")

# ==================== НАСТРОЙКИ ЛОГИРОВАНИЯ ====================
import logging

# Создаем логгер для config
logger = logging.getLogger(__name__)

def setup_logging():
    """Настройка логирования для всего приложения"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Проверяем среду выполнения
    environment = "Production" if os.getenv('RENDER') else "Development"
    logger.info(f"✅ Конфигурация загружена успешно")
    logger.info(f"✅ Среда: {environment}")
    logger.info(f"✅ Токен получен (первые 10 символов): {API_TOKEN[:10]}...")
    logger.info(f"✅ Файл данных пользователей: {USER_DATA_FILE}")
    logger.info(f"✅ Порт веб-сервера: {WEB_SERVER_PORT}")

# Автоматически настраиваем логирование при импорте
setup_logging()

# ==================== ПРОВЕРКА БОТА ====================
def check_bot_status():
    """Проверяет доступность бота через Telegram API"""
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{API_TOKEN}/getMe"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        data = response.json()
        
        if data.get("ok"):
            bot_info = data['result']
            logger.info(f"✅ Бот доступен: @{bot_info['username']} ({bot_info['first_name']})")
            return True
        else:
            logger.error(f"❌ Ошибка Telegram API: {data.get('description', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки бота: {e}")
        return False

# ==================== ЭКСПОРТИРУЕМЫЕ ПЕРЕМЕННЫЕ ====================
__all__ = [
    'API_TOKEN',
    'MAX_RETRIES',
    'RETRY_DELAY',
    'POLLING_TIMEOUT',
    'REQUEST_TIMEOUT',
    'MAX_MESSAGE_LENGTH',
    'USER_DATA_FILE',
    'AUTO_SAVE_INTERVAL',
    'WEB_SERVER_PORT',
    'WEB_SERVER_HOST',
    'WEB_SERVER_THREADS',
    'SELF_PING_URL',
    'SELF_PING_INTERVAL',
    'logger',
    'check_bot_status'
]
