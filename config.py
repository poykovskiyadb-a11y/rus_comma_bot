# config.py - безопасная конфигурация бота
import os
import sys
import logging

logger = logging.getLogger(__name__)

# Настройки в зависимости от среды
IS_RENDER = os.getenv('RENDER') is not None
IS_PRODUCTION = os.getenv('ENVIRONMENT') == 'production' or IS_RENDER

# Пытаемся загрузить переменные из .env файла (только для локальной разработки)
if not IS_PRODUCTION:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("✅ .env файл загружен (локальная разработка)")
    except ImportError:
        logger.warning("⚠️  python-dotenv не установлен, используем переменные окружения")

# Получаем токен из переменных окружения
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Проверяем, что токен существует
if not API_TOKEN:
    error_msg = """
❌ ОШИБКА: Токен бота не найден!

ПРИЧИНЫ И РЕШЕНИЯ:

1. Для локальной разработки:
   - Установите: pip install python-dotenv
   - Создайте .env файл с TELEGRAM_BOT_TOKEN=ваш_токен
   - НИКОГДА не загружайте .env в GitHub!

2. Для Render.com:
   - В Dashboard вашего сервиса → Environment
   - Добавьте переменную: TELEGRAM_BOT_TOKEN
   - Вставьте ваш токен (полученный от @BotFather)
   - Формат: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

3. Как получить токен:
   - Напишите @BotFather в Telegram
   - Отправьте /newbot
   - Следуйте инструкциям
   - Скопируйте токен
"""
    print("=" * 60)
    print(error_msg)
    print("=" * 60)
    
    # В продакшене логируем, но не падаем сразу (может быть временная проблема)
    if IS_PRODUCTION:
        logger.error("Токен бота не найден в продакшн среде!")
        # Ждем 30 секунд перед завершением, чтобы можно было увидеть логи
        import time
        time.sleep(30)
    sys.exit(1)

# Дополнительная проверка формата токена
def validate_token_format(token):
    """Проверяет, что токен похож на настоящий токен бота"""
    if not token:
        return False
    
    parts = token.split(':')
    if len(parts) != 2:
        return False
    
    if not parts[0].isdigit() or len(parts[0]) < 5:
        return False
    
    if len(parts[1]) < 20:
        return False
    
    return True

if not validate_token_format(API_TOKEN):
    warning_msg = """
⚠️  ВНИМАНИЕ: Токен не соответствует ожидаемому формату
Пример правильного токена: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
"""
    print(warning_msg)
    
    # На сервере останавливаемся, локально только предупреждаем
    if IS_PRODUCTION:
        logger.error("Некорректный формат токена в продакшн среде!")
        sys.exit(1)

# Логируем успешную загрузку (только начало токена для безопасности)
token_start = API_TOKEN[:min(10, len(API_TOKEN))]
logger.info(f"✅ Конфигурация загружена успешно")
logger.info(f"✅ Среда: {'Production' if IS_PRODUCTION else 'Development'}")
logger.info(f"✅ Токен получен (первые {len(token_start)} символов): {token_start}...")
