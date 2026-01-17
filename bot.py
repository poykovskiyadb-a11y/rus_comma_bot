# bot.py - главный файл Telegram-бота для тренировки запятой перед "и"
import asyncio
import json
import random
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties  # НОВОЕ ИМПОРТ

# Импортируем наши данные
from rules import RULE_TEXT
from examples import EXAMPLES

# --- НАСТРОЙКА ЛОГГИРОВАНИЯ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# --- ОБРАБОТЧИКИ ---
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

❓ *Вопрос:* Нужна ли запятая перед союзом *«и»* в этом предложении?
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

# --- АВТОСОХРАНЕНИЕ ---
async def auto_save():
    """Автоматическое сохранение данных каждые 5 минут"""
    while True:
        await asyncio.sleep(300)
        save_user_data(user_data)
        logger.info("Данные пользователей автосохранены")

# --- ЗАПУСК БОТА ---
# Добавьте в конец функции main():
async def main():
    print("=" * 50)
    print("БОТ ДЛЯ ТРЕНИРОВКИ ЗАПЯТОЙ ПЕРЕД 'И'")
    print("=" * 50)
    print(f"Загружено примеров: {len(EXAMPLES)}")
    print(f"Зарегистрировано пользователей: {len(user_data)}")
    print("Бот запускается...")
    print(f"Среда: {'Production' if os.getenv('RENDER') else 'Development'}")
    
    # Запускаем автосохранение в фоне
    asyncio.create_task(auto_save())
    
    # Запускаем бота с обработкой graceful shutdown
    try:
        await dp.start_polling(bot)
    finally:
        # Сохраняем данные при завершении
        save_user_data(user_data)
        print("Данные сохранены перед завершением")
        await bot.session.close()

# И обновите блок try-except в конце:
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Произошла ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("✅ Бот завершил работу")