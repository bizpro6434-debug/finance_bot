import sqlite3
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8649566547:AAFyicVC3WtJyH0z7PHjz7irL2VGOj-PKOw"

# --- СОСТОЯНИЯ ---
class TransactionForm(StatesGroup):
    choosing_type = State()
    choosing_category = State()
    entering_amount = State()
    entering_description = State()

# --- ИНИЦИАЛИЗАЦИЯ ---
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('finance.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            category TEXT,
            amount REAL,
            description TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_transaction(user_id, trans_type, category, amount, description):
    conn = sqlite3.connect('finance.db')
    cur = conn.cursor()
    date_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute('''
        INSERT INTO transactions (user_id, type, category, amount, description, date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, trans_type, category, amount, description, date_now))
    conn.commit()
    conn.close()

def get_stats(user_id, period):
    conn = sqlite3.connect('finance.db')
    cur = conn.cursor()
    
    now = datetime.now()
    if period == 'day':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    elif period == 'week':
        start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    elif period == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    else:
        start_date = '1970-01-01'

    cur.execute('''
        SELECT type, SUM(amount) FROM transactions
        WHERE user_id = ? AND date >= ?
        GROUP BY type
    ''', (user_id, start_date))
    
    results = cur.fetchall()
    conn.close()
    
    income = 0
    expense = 0
    for row in results:
        if row[0] == 'income':
            income = row[1] if row[1] else 0
        else:
            expense = row[1] if row[1] else 0
            
    balance = income - expense
    return income, expense, balance

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Доход", callback_data="add_income")],
        [InlineKeyboardButton(text="➖ Расход", callback_data="add_expense")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")]
    ])
    return keyboard

def get_category_keyboard(trans_type):
    if trans_type == 'income':
        categories = ["Зарплата", "Фриланс", "Подарок", "Другое"]
    else:
        categories = ["Еда", "Транспорт", "Развлечения", "Коммуналка", "Здоровье", "Другое"]
    
    buttons = [[InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")] for cat in categories]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_stats_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📆 Сегодня", callback_data="stats_day"),
         InlineKeyboardButton(text="📅 Неделя", callback_data="stats_week")],
        [InlineKeyboardButton(text="🗓 Месяц", callback_data="stats_month")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "💰 *Финансовый помощник*\n\nЯ помогу вести учёт доходов и расходов.\nИспользуйте кнопки:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "💰 *Главное меню*",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "stats")
async def show_stats_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📈 *Статистика*\n\nВыберите период:",
        reply_markup=get_stats_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("stats_"))
async def show_stats(callback: types.CallbackQuery):
    period = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    income, expense, balance = get_stats(user_id, period)
    
    period_names = {'day': 'сегодня', 'week': 'на этой неделе', 'month': 'в этом месяце'}
    
    text = f"📊 *Статистика {period_names[period]}*\n\n"
    text += f"✅ *Доходы:* {income:.2f} ₸\n"
    text += f"❌ *Расходы:* {expense:.2f} ₸\n"
    text += f"💵 *Баланс:* {balance:.2f} ₸"
    
    await callback.message.edit_text(text, reply_markup=get_stats_keyboard(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "add_income")
async def add_income(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(trans_type="income")
    await state.set_state(TransactionForm.choosing_category)
    await callback.message.edit_text(
        "💰 *Доход*\n\nВыберите категорию:",
        reply_markup=get_category_keyboard("income"),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "add_expense")
async def add_expense(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(trans_type="expense")
    await state.set_state(TransactionForm.choosing_category)
    await callback.message.edit_text(
        "💸 *Расход*\n\nВыберите категорию:",
        reply_markup=get_category_keyboard("expense"),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_"), TransactionForm.choosing_category)
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    await state.set_state(TransactionForm.entering_amount)
    
    await callback.message.edit_text(
        f"📌 *Категория:* {category}\n\n💵 Введите сумму (цифры):",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(TransactionForm.entering_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля:")
            return
    except ValueError:
        await message.answer("❌ Введите число (например: 1000 или 1500.50):")
        return
    
    await state.update_data(amount=amount)
    await state.set_state(TransactionForm.entering_description)
    await message.answer(
        f"💰 Сумма: {amount:.2f} ₸\n\n📝 Введите описание (или напишите 'пропустить'):"
    )

@dp.message(TransactionForm.entering_description)
async def process_description(message: types.Message, state: FSMContext):
    description = message.text
    if description.lower() == "пропустить":
description = ""
    
    data = await state.get_data()
    
    add_transaction(
        user_id=message.from_user.id,
        trans_type=data['trans_type'],
        category=data['category'],
        amount=data['amount'],
        description=description
    )
    
    type_emoji = "💰 Доход" if data['trans_type'] == 'income' else "💸 Расход"
    success_text = (
        f"✅ *Запись добавлена!*\n\n"
        f"{type_emoji}: {data['category']}\n"
        f"Сумма: {data['amount']:.2f} ₸\n"
        f"Описание: {description if description else '—'}"
    )
    
    await state.clear()
    await message.answer(success_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@dp.message()
async def unknown_message(message: types.Message):
    await message.answer("Используйте кнопки меню.", reply_markup=get_main_keyboard())

# --- ЗАПУСК ---
async def main():
    init_db()
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
