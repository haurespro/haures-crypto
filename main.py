import logging
from aiogram import Bot, Dispatcher, types, executor
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")

# إعدادات البوت
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# الاتصال بقاعدة البيانات
conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")
cur = conn.cursor()

# أوامر البوت
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer("👋 مرحبا بك! من فضلك أرسل بريدك الإلكتروني:")

# استقبال البريد الإلكتروني
@dp.message_handler(lambda message: "@" in message.text)
async def get_email(message: types.Message):
    user_id = message.from_user.id
    email = message.text
    cur.execute("INSERT INTO users (user_id, email) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET email = EXCLUDED.email", (user_id, email))
    conn.commit()
    await message.answer("✅ تم تسجيل بريدك الإلكتروني. الآن أرسل الكود السري.")

# استقبال الكود
@dp.message_handler(lambda message: message.text.isdigit())
async def get_code(message: types.Message):
    user_id = message.from_user.id
    code = message.text
    cur.execute("UPDATE users SET code = %s WHERE user_id = %s", (code, user_id))
    conn.commit()
    await message.answer("💸 أرسل الآن إثبات الدفع (لقطة شاشة).")

# استقبال لقطة الشاشة
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def get_payment_proof(message: types.Message):
    user_id = message.from_user.id
    file_id = message.photo[-1].file_id
    cur.execute("UPDATE users SET payment_proof = %s WHERE user_id = %s", (file_id, user_id))
    conn.commit()
    await message.answer("📥 تم حفظ إثبات الدفع بنجاح.\nنحن في انتظار التأكيد اليدوي.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
