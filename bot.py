import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)


def init_db():
    with sqlite3.connect("planner.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan_date TEXT,
                plan_text TEXT
            )
        ''')
        conn.commit()


def add_plan(user_id, date_str, text):
    with sqlite3.connect("planner.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO plans (user_id, plan_date, plan_text) VALUES (?, ?, ?)",
                       (user_id, date_str, text))
        conn.commit()


def get_plans(user_id, date_str):
    with sqlite3.connect("planner.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT plan_text FROM plans WHERE user_id = ? AND plan_date = ?", (user_id, date_str))
        return cursor.fetchall()


def clear_plans(user_id, date_str):
    with sqlite3.connect("planner.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM plans WHERE user_id = ? AND plan_date = ?", (user_id, date_str))
        conn.commit()


def get_week_keyboard():
    builder = InlineKeyboardBuilder()
    days_ukr = ["Пн", "Вв", "Ср", "Чт", "Пт", "Сб", "Нд"]
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())

    for i in range(7):
        current_date = start_of_week + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        prefix = "📍 " if current_date == today else ""
        label = f"{prefix}{days_ukr[i]} ({current_date.strftime('%d.%m')})"
        builder.button(text=label, callback_data=f"day_{date_str}")

    builder.adjust(2)
    return builder.as_markup()


def get_day_options(date_str):
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Додати план", callback_data=f"add_{date_str}")
    builder.button(text="🗑 Очистити цей день", callback_data=f"clear_{date_str}")
    builder.button(text="⬅️ Назад", callback_data="back_to_week")
    builder.adjust(1)
    return builder.as_markup()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Оберіть день:", reply_markup=get_week_keyboard())


@dp.callback_query(F.data == "back_to_week")
async def back_to_week(callback: types.CallbackQuery):
    await callback.message.edit_text("Оберіть день:", reply_markup=get_week_keyboard())


@dp.callback_query(F.data.startswith("day_"))
async def show_day_plans(callback: types.CallbackQuery):
    date_str = callback.data.split("_")[1]
    plans = get_plans(callback.from_user.id, date_str)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    text = f"📅 План на {date_obj.strftime('%d.%m.%Y')}:\n\n"
    if not plans:
        text += "Пусто"
    else:
        for i, p in enumerate(plans, 1):
            text += f"{i}. {p[0]}\n"
    await callback.message.edit_text(text, reply_markup=get_day_options(date_str))


user_waiting_input = {}


@dp.callback_query(F.data.startswith("add_"))
async def ask_plan_text(callback: types.CallbackQuery):
    date_str = callback.data.split("_")[1]
    user_waiting_input[callback.from_user.id] = date_str
    await callback.message.answer(f"Напишіть план на {date_str}:")
    await callback.answer()


@dp.message(F.text)
async def process_plan_input(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_waiting_input:
        date_str = user_waiting_input.pop(user_id)
        add_plan(user_id, date_str, message.text)
        await message.answer("Збережено", reply_markup=get_week_keyboard())
    else:
        await message.answer("Використовуйте меню", reply_markup=get_week_keyboard())


@dp.callback_query(F.data.startswith("clear_"))
async def clear_day(callback: types.CallbackQuery):
    date_str = callback.data.split("_")[1]
    clear_plans(callback.from_user.id, date_str)
    await callback.answer("Очищено")
    await show_day_plans(callback)


async def daily_notification():
    while True:
        now = datetime.now()
        if now.hour == 9 and now.minute == 0:
            date_str = now.strftime("%Y-%m-%d")
            with sqlite3.connect("planner.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT user_id FROM plans WHERE plan_date = ?", (date_str,))
                users = cursor.fetchall()
                for (user_id,) in users:
                    plans = get_plans(user_id, date_str)
                    if plans:
                        text = "☀️ Плани на сьогодні:\n\n"
                        for i, p in enumerate(plans, 1):
                            text += f"{i}. {p[0]}\n"
                        try:
                            await bot.send_message(user_id, text)
                        except:
                            pass
            await asyncio.sleep(61)
        await asyncio.sleep(30)


async def main():
    init_db()
    asyncio.create_task(daily_notification())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())