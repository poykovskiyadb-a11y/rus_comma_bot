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
from examples import EXAMPLES

USER_DATA_FILE = 'user_data.json'

def load_user_data():
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_data = load_user_data()

# --- ВЕБ-ЭНДПОИНТЫ (должны быть определены ДО импорта aiogram) ---
@app.route('/')
def home():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Бот для тренировки запятых</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .status {{ color: green; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>🤖 Бот для тренировки запятых перед "и"</h1>
        <p>Статус: <span class="status">✅ Активен</span></p>
        <p>Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Примеров в базе: {len(EXAMPLES)}</p>
        <p>Пользователей: {len(user_data)}</p>
        <hr>
        <p>🔄 Бот автоматически поддерживает активность каждые 5 минут</p>
        <p>🌐 Веб-сервер запущен и слушает порт</p>
        <p>🤖 Telegram бот работает в фоновом режиме</p>
        <p><a href="/ping">Проверить связь</a> | <a href="/health">Статус</a></p>
    </body>
    </html>
    """

@app.route('/ping')
def ping():
    logger.info("Получен ping запрос")
    return 'pong', 200

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "users": len(user_data),
        "examples": len(EXAMPLES)
    }), 200

# --- ЗАПУСК ВЕБ-СЕРВЕРА В ОТДЕЛЬНОМ ПОТОКЕ ---
def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Запуск веб-сервера на порту {port}")
    
    # Используем waitress для продакшена
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=port, threads=4)
    except ImportError:
        logger.warning("Waitress не установлен, используем dev-сервер")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- СИСТЕМА САМОПИНГА ---
class SelfPinger:
    def __init__(self):
        self.active = True
        self.count = 0
        
    def ping(self):
        try:
            url = f"https://{os.environ.get('RENDER_SERVICE_NAME', 'rus-comma-bot')}.onrender.com/ping"
            response = requests.get(url, timeout=10)
            self.count += 1
            logger.info(f"✅ Self-ping #{self.count}: {response.status_code}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Self-ping не удался: {e}")
            return False
    
    def start(self):
        def worker():
            # Ждем 30 секунд перед первым пингом
            time.sleep(30)
            while self.active:
                self.ping()
                # Пингуем каждые 5 минут
                time.sleep(300)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

# --- ТЕЛЕГРАМ БОТ (запускается после веб-сервера) ---
def run_telegram_bot():
    """Запускает Telegram бота в отдельном потоке"""
    try:
        import asyncio
        from aiogram import Bot, Dispatcher, types
        from aiogram.filters import Command
        from aiogram.utils.keyboard import ReplyKeyboardBuilder
        from aiogram.enums import ParseMode
        from aiogram.client.default import DefaultBotProperties
        from config import API_TOKEN
        from rules import RULE_TEXT
        
        # Инициализация бота
        bot = Bot(
            token=API_TOKEN, 
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        dp = Dispatcher()
        
        # Клавиатуры
        def get_main_keyboard():
            builder = ReplyKeyboardBuilder()
            builder.add(types.KeyboardButton(text="📖 Правило"))
            builder.add(types.KeyboardButton(text="🚀 Начать тест"))
            builder.add(types.KeyboardButton(text="📊 Статистика"))
            builder.add(types.KeyboardButton(text="💪 Работа над ошибками"))
            builder.adjust(2, 2)
            return builder.as_markup(resize_keyboard=True)
        
        def get_test_keyboard():
            builder = ReplyKeyboardBuilder()
            builder.add(types.KeyboardButton(text="✅ Да, нужна"))
            builder.add(types.KeyboardButton(text="❌ Нет, не нужна"))
            builder.add(types.KeyboardButton(text="🔙 В меню"))
            builder.adjust(2, 1)
            return builder.as_markup(resize_keyboard=True)
        
        # Обработчики
        @dp.message(Command("start"))
        async def cmd_start(message: types.Message):
            user_id = str(message.from_user.id)
            user_name = message.from_user.first_name
            
            logger.info(f"Пользователь {user_name} (ID: {user_id}) запустил бота")
            
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
            await message.answer(welcome_text, reply_markup=get_main_keyboard())
        
        @dp.message(lambda message: message.text == "📖 Правило")
        async def show_rule(message: types.Message):
            await message.answer(RULE_TEXT)
        
        @dp.message(lambda message: message.text == "📊 Статистика")
        async def show_stats(message: types.Message):
            user_id = str(message.from_user.id)
            
            if user_id in user_data:
                data = user_data[user_id]
                total = data["total_tests"]
                correct = data["correct_answers"]
                
                if total > 0:
                    accuracy = (correct / total) * 100
                    stats_text = f"""
*📊 Ваша статистика*

👤 Имя: {data['user_name']}
✅ Правильных ответов: {correct}
❌ Неправильных ответов: {data['incorrect_answers']}
📈 Всего тестов: {total}
🎯 Точность: {accuracy:.1f}%
🔄 Прогресс: {correct} из {len(EXAMPLES)} примеров освоено
"""
                else:
                    stats_text = "Вы ещё не прошли ни одного теста. Нажмите '🚀 Начать тест'!"
            else:
                stats_text = "Статистика не найдена. Нажмите /start"
            
            await message.answer(stats_text)
        
        @dp.message(lambda message: message.text == "💪 Работа над ошибками")
        async def show_mistakes(message: types.Message):
            user_id = str(message.from_user.id)
            
            if user_id not in user_data or not user_data[user_id]["mistakes"]:
                await message.answer("🎉 У вас пока нет ошибок! Продолжайте в том же духе!")
                return
            
            mistakes = user_data[user_id]["mistakes"]
            recent_mistakes = mistakes[-10:] if len(mistakes) > 10 else mistakes
            
            mistakes_text = "💪 *Работа над ошибками*\n\n"
            mistakes_text += f"Всего ошибок: {len(mistakes)}\n\n"
            
            for i, example_idx in enumerate(recent_mistakes, 1):
                example, correct_answer, explanation = EXAMPLES[example_idx]
                
                if correct_answer:
                    parts = example.rsplit(" и ", 1)
                    formatted_example = parts[0] + ", и " + parts[1]
                else:
                    formatted_example = example
                
                mistakes_text += f"{i}. `{formatted_example}`\n"
                mistakes_text += f"   📝 *Объяснение:* {explanation}\n\n"
            
            builder = ReplyKeyboardBuilder()
            builder.add(types.KeyboardButton(text="🧹 Очистить историю ошибок"))
            builder.add(types.KeyboardButton(text="🔙 В меню"))
            builder.adjust(2)
            
            await message.answer(mistakes_text, reply_markup=builder.as_markup(resize_keyboard=True))
        
        @dp.message(lambda message: message.text == "🧹 Очистить историю ошибок")
        async def clear_mistakes(message: types.Message):
            user_id = str(message.from_user.id)
            
            if user_id in user_data:
                user_data[user_id]["mistakes"] = []
                save_user_data(user_data)
                await message.answer("✅ История ошибок очищена!", reply_markup=get_main_keyboard())
            else:
                await message.answer("❌ Ошибка: данные пользователя не найдены", reply_markup=get_main_keyboard())
        
        @dp.message(lambda message: message.text == "🚀 Начать тест")
        async def start_test(message: types.Message):
            user_id = str(message.from_user.id)
            
            if user_id not in user_data:
                await cmd_start(message)
                return
            
            example_index = random.randint(0, len(EXAMPLES) - 1)
            user_data[user_id]["current_example"] = example_index
            save_user_data(user_data)
            
            example_text, correct_answer, explanation = EXAMPLES[example_index]
            
            question_text = f"""
*Пример {example_index + 1} из {len(EXAMPLES)}*

`{example_text}`

❓ *Вопрос:* Нужна ли запятой перед союзом *«и»* в этом предложении?
"""
            await message.answer(question_text, reply_markup=get_test_keyboard())
        
        @dp.message(lambda message: message.text in ["✅ Да, нужна", "❌ Нет, не нужна"])
        async def check_answer(message: types.Message):
            user_id = str(message.from_user.id)
            
            if user_id not in user_data or "current_example" not in user_data[user_id]:
                await message.answer("❌ Сначала начните тест, нажав '🚀 Начать тест'", reply_markup=get_main_keyboard())
                return
            
            example_index = user_data[user_id]["current_example"]
            example_text, correct_answer, explanation = EXAMPLES[example_index]
            user_answer = (message.text == "✅ Да, нужна")
            
            del user_data[user_id]["current_example"]
            user_data[user_id]["total_tests"] += 1
            is_correct = (user_answer == correct_answer)
            
            if is_correct:
                user_data[user_id]["correct_answers"] += 1
            else:
                user_data[user_id]["incorrect_answers"] += 1
                if example_index not in user_data[user_id]["mistakes"]:
                    user_data[user_id]["mistakes"].append(example_index)
            
            total = user_data[user_id]["total_tests"]
            correct = user_data[user_id]["correct_answers"]
            user_data[user_id]["accuracy"] = (correct / total * 100) if total > 0 else 0
            user_data[user_id]["last_active"] = datetime.now().isoformat()
            save_user_data(user_data)
            
            if correct_answer:
                parts = example_text.rsplit(" и ", 1)
                formatted_example = parts[0] + ", и " + parts[1]
            else:
                formatted_example = example_text
            
            result_text = f"""
{'✅ *ПРАВИЛЬНО!*' if is_correct else '❌ *НЕПРАВИЛЬНО*'}

*Ваш ответ:* {"✅ Да, нужна" if user_answer else "❌ Нет, не нужна"}
*Правильный ответ:* {"✅ Да, нужна" if correct_answer else "❌ Нет, не нужна"}

*Правильный вариант:*
`{formatted_example}`

*Объяснение:*
{explanation}

*Ваша статистика:*
Правильно: {user_data[user_id]["correct_answers"]} из {user_data[user_id]["total_tests"]}
Точность: {user_data[user_id]["accuracy"]:.1f}%
"""
            await message.answer(result_text)
            await asyncio.sleep(2)
            
            builder = ReplyKeyboardBuilder()
            builder.add(types.KeyboardButton(text="➡️ Следующий вопрос"))
            builder.add(types.KeyboardButton(text="📊 Статистика"))
            builder.add(types.KeyboardButton(text="🔙 В меню"))
            builder.adjust(2, 1)
            
            await message.answer("Хотите продолжить тренировку?", reply_markup=builder.as_markup(resize_keyboard=True))
        
        @dp.message(lambda message: message.text == "➡️ Следующий вопрос")
        async def next_question(message: types.Message):
            await start_test(message)
        
        @dp.message(lambda message: message.text == "🔙 В меню")
        async def back_to_menu(message: types.Message):
            user_id = str(message.from_user.id)
            
            if user_id in user_data and "current_example" in user_data[user_id]:
                del user_data[user_id]["current_example"]
                save_user_data(user_data)
            
            await message.answer("Возвращаемся в главное меню...", reply_markup=get_main_keyboard())
        
        @dp.message()
        async def unknown_message(message: types.Message):
            await message.answer("Я не понимаю эту команду. Используйте меню ниже:", reply_markup=get_main_keyboard())
        
        # Автосохранение
        async def auto_save():
            while True:
                await asyncio.sleep(300)
                save_user_data(user_data)
                logger.info("Данные пользователей автосохранены")
        
        # Основная функция бота
        async def main_bot():
            logger.info("🤖 Запуск Telegram бота...")
            
            # Запускаем автосохранение
            asyncio.create_task(auto_save())
            
            # Запускаем бота
            await dp.start_polling(bot)
        
        # Запускаем asyncio в отдельном потоке
        asyncio.run(main_bot())
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске Telegram бота: {e}")
        import traceback
        traceback.print_exc()

# --- ГЛАВНАЯ ФУНКЦИЯ ---
def main():
    print("=" * 60)
    print("🚀 ЗАПУСК СИСТЕМЫ")
    print("=" * 60)
    print(f"📝 Примеров в базе: {len(EXAMPLES)}")
    print(f"👥 Пользователей: {len(user_data)}")
    print(f"🌐 Среда: {'RENDER.com' if os.getenv('RENDER') else 'Локальная'}")
    print("=" * 60)
    
    # 1. Сначала запускаем самопинг
    pinger = SelfPinger()
    pinger.start()
    logger.info("✅ Self-pinger запущен")
    
    # 2. Запускаем Telegram бота в основном потоке (НЕ в отдельном!)
logger.info("✅ Запуск Telegram бота в основном потоке...")
run_telegram_bot()  # <-- ВЫЗОВ НЕПОСРЕДСТВЕННО, БЕЗ threading.Thread
    
    # 3. Запускаем веб-сервер в ОСНОВНОМ потоке
    logger.info("✅ Запуск веб-сервера...")
    run_web_server()

if __name__ == "__main__":
    main()
