# bot.py - главный файл Telegram-бота с веб-сервером
import os
import json
import random
import logging
import threading
import time
import requests
import sys
import socket
import asyncio
import traceback
from datetime import datetime
from flask import Flask, jsonify

# ===== НОВЫЙ КОД: ПРОВЕРКА УНИКАЛЬНОСТИ ПОРТА =====
def is_port_in_use(port):
    """Проверяет, занят ли порт другим процессом"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

# Ждем, если порт занят (это может быть предыдущий инстанс)
if os.getenv('RENDER'):
    port = int(os.environ.get('PORT', 10000))
    max_wait = 30  # максимум 30 секунд ожидания
    wait_time = 0
    
    while is_port_in_use(port) and wait_time < max_wait:
        print(f"⚠️  Порт {port} занят, ждем... ({wait_time}/{max_wait} сек)")
        time.sleep(2)
        wait_time += 2
    
    if wait_time >= max_wait:
        print("❌ Не удалось дождаться освобождения порта. Выход.")
        sys.exit(1)
# ===== КОНЕЦ НОВОГО КОДА =====

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- СОЗДАЕМ FLASK ПРИЛОЖЕНИЕ ПЕРВЫМ ---
app = Flask(__name__)

# Загружаем данные сразу
try:
    from examples import EXAMPLES
    logger.info(f"✅ Загружено {len(EXAMPLES)} примеров")
except ImportError as e:
    logger.error(f"❌ Не удалось загрузить examples.py: {e}")
    EXAMPLES = []

USER_DATA_FILE = 'user_data.json'

def load_user_data():
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"✅ Данные пользователей загружены: {len(data)} пользователей")
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("Файл user_data.json не найден, создаем новый")
        return {}

def save_user_data(data):
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Данные сохранены: {len(data)} пользователей")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения данных: {e}")

user_data = load_user_data()
user_data_lock = threading.Lock()

# --- ВЕБ-ЭНДПОИНТЫ ---
@app.route('/')
def home():
    with user_data_lock:
        user_count = len(user_data)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Бот для тренировки запятых</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .status {{ color: green; font-weight: bold; }}
            .error {{ color: red; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>🤖 Бот для тренировки запятых перед "и"</h1>
        <p>Статус: <span class="status">✅ Активен</span></p>
        <p>Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Примеров в базе: {len(EXAMPLES)}</p>
        <p>Пользователей: {user_count}</p>
        <hr>
        <p>🔄 Бот автоматически поддерживает активность каждые 5 минут</p>
        <p>🌐 Веб-сервер запущен и слушает порт</p>
        <p>🤖 Telegram бот: <span class="{'status' if bot_running else 'error'}">{'✅ Работает' if bot_running else '❌ Остановлен'}</span></p>
        <p><a href="/ping">Проверить связь</a> | <a href="/health">Статус</a> | <a href="/restart_bot">Перезапустить бота</a></p>
    </body>
    </html>
    """

@app.route('/ping')
def ping():
    logger.info("Получен ping запрос")
    return 'pong', 200

@app.route('/health')
def health():
    with user_data_lock:
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "users": len(user_data),
            "examples": len(EXAMPLES),
            "bot_running": bot_running,
            "bot_last_check": bot_last_check.isoformat() if bot_last_check else None
        }), 200

@app.route('/restart_bot')
def restart_bot():
    logger.info("Ручной перезапуск бота запрошен через веб-интерфейс")
    if telegram_bot and hasattr(telegram_bot, 'restart'):
        telegram_bot.restart()
        return "🔄 Бот перезапускается...", 200
    return "❌ Не удалось перезапустить бота", 500

# --- СИСТЕМА МОНИТОРИНГА БОТА ---
bot_running = False
bot_last_check = None
bot_check_lock = threading.Lock()

class BotMonitor:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.active = True
        
    def start(self):
        def monitor():
            global bot_running, bot_last_check
            while self.active:
                try:
                    # Проверяем статус бота
                    with bot_check_lock:
                        bot_last_check = datetime.now()
                        # Здесь можно добавить дополнительную проверку
                    
                    time.sleep(60)  # Проверяем каждую минуту
                except Exception as e:
                    logger.error(f"Ошибка в мониторе бота: {e}")
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        logger.info("✅ Монитор бота запущен")
        return thread

# --- СИСТЕМА САМОПИНГА ---
class SelfPinger:
    def __init__(self):
        self.active = True
        self.count = 0
        
    def ping(self):
        try:
            service_name = os.environ.get('RENDER_SERVICE_NAME', 'rus-comma-bot')
            url = f"https://{service_name}.onrender.com/ping"
            response = requests.get(url, timeout=10)
            self.count += 1
            logger.info(f"✅ Self-ping #{self.count}: {response.status_code}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Self-ping не удался: {e}")
            return False
    
    def start(self):
        def worker():
            time.sleep(30)
            while self.active:
                self.ping()
                time.sleep(300)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        logger.info("✅ Self-pinger запущен")
        return thread

# --- ТЕЛЕГРАМ БОТ ---
class TelegramBot:
    def __init__(self):
        self.bot = None
        self.dp = None
        self.active = True
        self.session = None
        self.polling_task = None
        
    def initialize(self):
        try:
            from aiogram import Bot, Dispatcher, types
            from aiogram.filters import Command
            from aiogram.utils.keyboard import ReplyKeyboardBuilder
            from aiogram.enums import ParseMode
            from aiogram.client.default import DefaultBotProperties
            from aiogram.client.session.aiohttp import AiohttpSession
            
            from config import API_TOKEN
            from rules import RULE_TEXT
            
            if not API_TOKEN:
                logger.error("❌ API_TOKEN не найден в config.py")
                return False
                
            # Используем сессию с таймаутами
            self.session = AiohttpSession()
            
            self.bot = Bot(
                token=API_TOKEN,
                session=self.session,
                default=DefaultBotProperties(
                    parse_mode=ParseMode.MARKDOWN,
                    link_preview_is_disabled=True
                )
            )
            self.dp = Dispatcher()
            
            self._setup_handlers(RULE_TEXT)
            logger.info("✅ Telegram бот инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _setup_handlers(self, RULE_TEXT):
        from aiogram import types
        from aiogram.filters import Command
        
        @self.dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            user_id = str(message.from_user.id)
            user_name = message.from_user.first_name
            
            logger.info(f"Пользователь {user_name} (ID: {user_id}) запустил бота")
            
            with user_data_lock:
                if user_id not in user_data:
                    user_data[user_id] = {
                        "user_name": user_name,
                        "total_tests": 0,
                        "correct_answers": 0,
                        "incorrect_answers": 0,
                        "accuracy": 0.0,
                        "last_active": datetime.now().isoformat(),
                        "mistakes": []
                    }
                    save_user_data(user_data)
            
            welcome_text = f"""
Привет, {user_name}! 👋

*Я бот-тренажёр по русскому языку!*

Я помогу тебе научиться правильно ставить запятую перед союзом *«И»*.

📊 *Что я умею:*
• Объяснять правило с примерами
• Проводить тесты (у нас {len(EXAMPLES)} примеров!)
• Показывать статистику
• Помогать работать над ошибками

Выбери действие в меню ниже:
"""
            await message.answer(welcome_text, reply_markup=self._get_main_keyboard())
        
        # ... остальные обработчики остаются без изменений ...
        # (используйте ваш существующий код обработчиков)
    
    async def run_polling(self):
        """Запуск polling с обработкой ошибок"""
        global bot_running
        
        retry_count = 0
        max_retries = 10
        
        while self.active and retry_count < max_retries:
            try:
                logger.info("🤖 Запуск polling Telegram бота...")
                bot_running = True
                
                await self.dp.start_polling(
                    self.bot,
                    handle_signals=False,
                    skip_updates=True,
                    polling_timeout=30,
                    allowed_updates=["message", "callback_query"]
                )
                
            except Exception as e:
                bot_running = False
                retry_count += 1
                
                if "Flood control" in str(e):
                    wait_time = min(60 * retry_count, 300)  # Максимум 5 минут
                    logger.error(f"⚠️ Flood control, ждем {wait_time} секунд...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ Ошибка в polling (попытка {retry_count}/{max_retries}): {e}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(10 * retry_count)
            
        logger.error("❌ Достигнуто максимальное количество попыток, бот остановлен")
        bot_running = False
    
    async def run(self):
        """Основной запуск бота"""
        if not self.initialize():
            logger.error("❌ Не удалось инициализировать Telegram бота")
            return
        
        # Запускаем автосохранение
        asyncio.create_task(self._auto_save())
        
        # Запускаем polling
        await self.run_polling()
    
    async def _auto_save(self):
        """Автосохранение данных пользователей"""
        while self.active:
            await asyncio.sleep(300)
            with user_data_lock:
                save_user_data(user_data)
                logger.info("Данные пользователей автосохранены")
    
    def restart(self):
        """Перезапуск бота"""
        logger.info("🔄 Перезапуск Telegram бота...")
        self.stop()
        time.sleep(2)
        self.active = True
        self.run_in_thread()
    
    def stop(self):
        """Остановка бота"""
        logger.info("🛑 Остановка Telegram бота...")
        self.active = False
        if self.polling_task:
            self.polling_task.cancel()
        if self.session:
            asyncio.run(self.session.close())
    
    def run_in_thread(self):
        """Запуск бота в отдельном потоке"""
        def run_async():
            try:
                asyncio.run(self.run())
            except Exception as e:
                logger.error(f"❌ Критическая ошибка в Telegram боте: {e}")
                logger.error(traceback.format_exc())
                global bot_running
                bot_running = False
        
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        logger.info("✅ Telegram бот запущен в отдельном потоке")
        return thread

# --- ЗАПУСК ВЕБ-СЕРВЕРА ---
def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Запуск веб-сервера на порту {port}")
    
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=port, threads=4)
    except ImportError:
        logger.warning("Waitress не установлен, используем dev-сервер")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- ГЛАВНАЯ ФУНКЦИЯ ---
def main():
    print("=" * 60)
    print("🚀 ЗАПУСК СИСТЕМЫ")
    print("=" * 60)
    print(f"📝 Примеров в базе: {len(EXAMPLES)}")
    
    with user_data_lock:
        print(f"👥 Пользователей: {len(user_data)}")
    
    print(f"🌐 Среда: {'RENDER.com' if os.getenv('RENDER') else 'Локальная'}")
    print("=" * 60)
    
    # Глобальные переменные
    global telegram_bot, bot_running, bot_last_check
    telegram_bot = None
    bot_running = False
    bot_last_check = datetime.now()
    
    # 1. Запускаем самопинг
    pinger = SelfPinger()
    pinger.start()
    logger.info("✅ Self-pinger запущен")
    
    # 2. Создаем и запускаем Telegram бота
    telegram_bot = TelegramBot()
    bot_thread = telegram_bot.run_in_thread()
    
    # 3. Запускаем монитор бота
    monitor = BotMonitor(telegram_bot)
    monitor.start()
    
    # 4. Запускаем веб-сервер
    logger.info("✅ Запуск веб-сервера в основном потоке...")
    run_web_server()

if __name__ == "__main__":
    main()
