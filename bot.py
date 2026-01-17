# bot.py - главный файл Telegram-бота для тренировки запятой перед "и" с самопинингом
import asyncio
import json
import random
import logging
import os
import sys
import time
import threading
import requests
import atexit
import signal
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Импортируем наши данные
from rules import RULE_TEXT
from examples import EXAMPLES

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- КЛАСС ДЛЯ САМОПИНГА И ВЕБ-СЕРВЕРА ---
class HealthMonitor:
    """Класс для поддержания активности бота и веб-сервера"""
    
    def __init__(self):
        self.active = True
        self.ping_count = 0
        self.last_ping = None
        self.last_success = None
        self.errors = 0
        self.max_errors = 5
        self.ping_urls = [
            "https://rus-comma-bot.onrender.com",
            "http://rus-comma-bot.onrender.com",
            "https://rus-comma-bot.onrender.com/ping"
        ]
        
    def ping_self(self):
        """Пингует сервер бота"""
        try:
            for url in self.ping_urls:
                try:
                    start_time = time.time()
                    response = requests.get(url, timeout=10)
                    end_time = time.time()
                    
                    if response.status_code == 200:
                        self.ping_count += 1
                        self.last_ping = datetime.now()
                        self.last_success = datetime.now()
                        self.errors = 0  # Сбрасываем счетчик ошибок
                        
                        logger.info(f"✅ Self-ping #{self.ping_count} успешен: {url} "
                                   f"({(end_time - start_time)*1000:.0f}ms)")
                        return True
                except requests.exceptions.RequestException:
                    continue
            
            self.errors += 1
            logger.warning(f"❌ Self-ping #{self.ping_count + 1} не удался. Ошибок подряд: {self.errors}")
            
            if self.errors >= self.max_errors:
                logger.error(f"🚨 Достигнут максимум ошибок ({self.max_errors}). Требуется проверка.")
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при self-ping: {e}")
            self.errors += 1
            return False
    
    def keep_alive_loop(self):
        """Бесконечный цикл для поддержания активности"""
        logger.info("🔄 Запуск цикла keep-alive...")
        
        # Ждем 30 секунд перед первым пингом (даем серверу запуститься)
        time.sleep(30)
        
        while self.active:
            try:
                # Пингуем каждые 8 минут (480 секунд)
                # Это гарантирует, что Render не уснет (15 минут бездействия)
                self.ping_self()
                
                # Засыпаем до следующего пинга
                time.sleep(480)
                
            except KeyboardInterrupt:
                logger.info("🛑 Keep-alive остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"⚠️ Ошибка в keep-alive цикле: {e}")
                time.sleep(60)  # Ждем минуту при ошибке
    
    def get_status(self):
        """Возвращает статус монитора"""
        return {
            "active": self.active,
            "ping_count": self.ping_count,
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "errors": self.errors,
            "max_errors": self.max_errors
        }
    
    def stop(self):
        """Останавливает монитор"""
        self.active = False
        logger.info("🛑 HealthMonitor остановлен")

# Создаем глобальный экземпляр монитора
health_monitor = HealthMonitor()

# --- ПРОСТОЙ ВЕБ-СЕРВЕР ---
def run_web_server():
    """Запускает простой веб-сервер для Render.com"""
    from flask import Flask
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        status = health_monitor.get_status()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>🤖 Бот для тренировки запятых перед "и"</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .status {{ padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .healthy {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
                .warning {{ background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }}
                .error {{ background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
                .card {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 15px; margin: 10px 0; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
            </style>
        </head>
        <body>
            <h1>🤖 Бот для тренировки запятых перед "и"</h1>
            
            <div class="status {'healthy' if status['errors'] == 0 else 'warning' if status['errors'] < 3 else 'error'}">
                <h2>Статус: {'✅ Активен' if status['errors'] == 0 else '⚠️ Есть проблемы' if status['errors'] < 3 else '❌ Критический'}</h2>
                <p>Последний успешный пинг: {status['last_success'] or 'Никогда'}</p>
            </div>
            
            <div class="card">
                <h3>📊 Статистика мониторинга</h3>
                <div class="stats">
                    <div>Всего пингов: <strong>{status['ping_count']}</strong></div>
                    <div>Ошибок подряд: <strong>{status['errors']}</strong></div>
                    <div>Макс. ошибок: <strong>{status['max_errors']}</strong></div>
                    <div>Статус: <strong>{'🟢 Активен' if health_monitor.active else '🔴 Остановлен'}</strong></div>
                </div>
            </div>
            
            <div class="card">
                <h3>🔗 Ссылки</h3>
                <ul>
                    <li><a href="/ping">Проверить связь (/ping)</a></li>
                    <li><a href="/health">Детальный статус (/health)</a></li>
                    <li><a href="/manual-ping">Ручной пинг (/manual-ping)</a></li>
                    <li><a href="/bot-status">Статус бота (/bot-status)</a></li>
                </ul>
            </div>
            
            <div class="card">
                <h3>ℹ️ Информация</h3>
                <p>Этот бот автоматически пингует себя каждые 8 минут, чтобы Render.com не останавливал его через 15 минут неактивности.</p>
                <p>Для проверки запятых пишите боту в Telegram: <a href="https://t.me/rus_comma_bot">@rus_comma_bot</a></p>
            </div>
            
            <footer style="margin-top: 30px; text-align: center; color: #6c757d;">
                <p>🔄 Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </footer>
        </body>
        </html>
        """
    
    @app.route('/ping')
    def ping():
        """Простой эндпоинт для проверки связи"""
        health_monitor.ping_self()
        return 'pong', 200
    
    @app.route('/health')
    def health():
        """Детальный статус здоровья"""
        import psutil
        import json as json_module
        
        status = health_monitor.get_status()
        bot_status = {
            "status": "healthy" if status['errors'] == 0 else "degraded" if status['errors'] < 3 else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "monitor": status,
            "system": {
                "memory_usage_mb": psutil.Process().memory_info().rss / 1024 / 1024,
                "cpu_percent": psutil.cpu_percent(),
                "uptime_seconds": time.time() - psutil.boot_time(),
            },
            "bot": {
                "users_count": len(user_data),
                "examples_count": len(EXAMPLES),
                "total_tests": sum(u.get('total_tests', 0) for u in user_data.values()),
            }
        }
        
        return json_module.dumps(bot_status, indent=2, ensure_ascii=False), 200, {'Content-Type': 'application/json'}
    
    @app.route('/manual-ping')
    def manual_ping():
        """Ручной пинг с деталями"""
        success = health_monitor.ping_self()
        status = health_monitor.get_status()
        
        return f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial;">
            <h1>{"✅ Пинг успешен" if success else "❌ Пинг не удался"}</h1>
            <pre>{json.dumps(status, indent=2, ensure_ascii=False)}</pre>
            <p><a href="/">На главную</a></p>
        </body>
        </html>
        """
    
    @app.route('/bot-status')
    def bot_status():
        """Статус бота с пользовательской статистикой"""
        total_users = len(user_data)
        active_users = sum(1 for u in user_data.values() 
                          if datetime.fromisoformat(u['last_active']).timestamp() > time.time() - 86400)
        total_tests = sum(u.get('total_tests', 0) for u in user_data.values())
        
        return f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial;">
            <h1>📊 Статистика бота</h1>
            <div class="stats">
                <p><strong>Всего пользователей:</strong> {total_users}</p>
                <p><strong>Активных пользователей (24ч):</strong> {active_users}</p>
                <p><strong>Всего пройденных тестов:</strong> {total_tests}</p>
                <p><strong>Примеров в базе:</strong> {len(EXAMPLES)}</p>
            </div>
            <p><a href="/">На главную</a></p>
        </body>
        </html>
        """
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Запуск веб-сервера на порту {port}")
    
    # Используем waitress для продакшена, а не дебаг сервер Flask
    if os.getenv('RENDER'):
        from waitress import serve
        serve(app, host='0.0.0.0', port=port)
    else:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- НАСТРОЙКА БОТА ---
from config import API_TOKEN

# СОЗДАЕМ БОТА ПО-НОВОМУ для aiogram 3.7.0+
bot = Bot(
    token=API_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()

# --- ХРАНЕНИЕ ДАННЫХ ---
USER_DATA_FILE = 'user_data.json'

def load_user_data():
    """Загружает данные пользователей из файла JSON"""
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_user_data(data):
    """Сохраняет данные пользователей в файл JSON"""
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_data = load_user_data()

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    """Создает главное меню"""
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="📖 Правило"))
    builder.add(types.KeyboardButton(text="🚀 Начать тест"))
    builder.add(types.KeyboardButton(text="📊 Статистика"))
    builder.add(types.KeyboardButton(text="💪 Работа над ошибками"))
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_test_keyboard():
    """Клавиатура для теста"""
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="✅ Да, нужна"))
    builder.add(types.KeyboardButton(text="❌ Нет, не нужна"))
    builder.add(types.KeyboardButton(text="🔙 В меню"))
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

# --- ОБРАБОТЧИКИ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обрабатывает команду /start"""
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

@dp.message(Command("ping"))
async def bot_ping(message: types.Message):
    """Проверка связи с ботом"""
    await message.answer("🏓 Понг! Бот работает исправно.")

@dp.message(Command("status"))
async def bot_status(message: types.Message):
    """Показать статус бота"""
    status = health_monitor.get_status()
    status_text = f"""
📊 *Статус системы*

🔄 Self-ping:
• Всего пингов: {status['ping_count']}
• Последний: {status['last_ping'] or 'Никогда'}
• Ошибок подряд: {status['errors']}/{status['max_errors']}

🤖 Бот:
• Пользователей: {len(user_data)}
• Примеров: {len(EXAMPLES)}
• Тестов: {sum(u.get('total_tests', 0) for u in user_data.values())}

🕐 Время: {datetime.now().strftime('%H:%M:%S')}

Статус: {'✅ Нормальный' if status['errors'] == 0 else '⚠️ Предупреждение' if status['errors'] < 3 else '❌ Проблемы'}
"""
    await message.answer(status_text)

@dp.message()
async def unknown_message(message: types.Message):
    await message.answer("Я не понимаю эту команду. Используйте меню ниже:", reply_markup=get_main_keyboard())

# --- АВТОСОХРАНЕНИЕ ---
async def auto_save():
    """Автоматическое сохранение данных каждые 5 минут"""
    while True:
        await asyncio.sleep(300)
        save_user_data(user_data)
        logger.info("Данные пользователей автосохранены")

# --- ОБРАБОТЧИКИ ЗАВЕРШЕНИЯ ---
def cleanup():
    """Очистка перед завершением работы"""
    logger.info("🧹 Выполняется очистка перед завершением...")
    health_monitor.stop()
    save_user_data(user_data)
    logger.info("✅ Очистка завершена")

# Регистрируем обработчики завершения
atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda s, f: (cleanup(), sys.exit(0)))
signal.signal(signal.SIGINT, lambda s, f: (cleanup(), sys.exit(0)))

# --- ЗАПУСК ВСЕГО ---
async def main():
    print("=" * 60)
    print("🤖 БОТ ДЛЯ ТРЕНИРОВКИ ЗАПЯТОЙ ПЕРЕД 'И'")
    print("=" * 60)
    print(f"📝 Примеров: {len(EXAMPLES)}")
    print(f"👥 Пользователей: {len(user_data)}")
    print(f"🌐 Среда: {'RENDER.com' if os.getenv('RENDER') else 'Локальная'}")
    print("🚀 Запуск...")
    print("=" * 60)
    
    # Запускаем веб-сервер в отдельном потоке
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("Веб-сервер запущен в отдельном потоке")
    
    # Запускаем keep-alive в отдельном потоке
    keep_alive_thread = threading.Thread(target=health_monitor.keep_alive_loop, daemon=True)
    keep_alive_thread.start()
    logger.info("Keep-alive монитор запущен")
    
    # Запускаем автосохранение
    asyncio.create_task(auto_save())
    
    # Запускаем бота
    try:
        await dp.start_polling(bot)
    finally:
        cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("✅ Работа завершена")
