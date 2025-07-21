import logging
from aiogram import Bot, Dispatcher, executor, types
import os
import psycopg2
from aiogram.types import InputFile

# إعدادات البوت
API_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# إعداد اللوغ
logging.basicConfig(level=logging.INFO)

# إنشاء كائنات البوت والديسباتشر
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# الاتصال بقاعدة البيانات
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# إنشاء الجدول إن لم يكن موجودًا
cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT,
        email TEXT,
        code TEXT,
        screenshot_file_id TEXT,
        confirmed BOOLEAN DEFAULT FALSE
    )
""")
conn.commit()


@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer(
        "🎓 مرحبًا بك في *برنامج Haures التعليمي المجاني*\n\n"
        "📧 الرجاء إرسال بريدك الإلكتروني للمتابعة.",
        parse_mode="Markdown"
    )


@dp.message_handler(lambda message: "@" in message.text or ".com" in message.text)
async def handle_email(message: types.Message):
    user_id = message.from_user.id
    email = message.text.strip()

    # حفظ البريد
    cur.execute("INSERT INTO users (telegram_id, email) VALUES (%s, %s) ON CONFLICT (telegram_id) DO NOTHING", (user_id, email))
    conn.commit()

    await message.answer("✅ تم تسجيل البريد الإلكتروني بنجاح!\n\n🔐 الآن، أرسل الرمز السري الذي حصلت عليه.")


@dp.message_handler(lambda message: len(message.text.strip()) >= 4)
async def handle_code(message: types.Message):
    user_id = message.from_user.id
    code = message.text.strip()

    # تحديث الرمز
    cur.execute("UPDATE users SET code = %s WHERE telegram_id = %s", (code, user_id))
    conn.commit()

    await message.answer(
        "💸 لدفع الاشتراك، أرسل USDT (TRC20) إلى العنوان التالي:\n\n"
        "`TXC4bZayv2YpEGvVuUoZmAo9ZHe1Z4V6hf`\n\n"
        "📸 بعد الدفع، أرسل لقطة شاشة كدليل.",
        parse_mode="Markdown"
    )


@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_screenshot(message: types.Message):
    user_id = message.from_user.id
    file_id = message.photo[-1].file_id

    # تحديث لقطة الشاشة
    cur.execute("UPDATE users SET screenshot_file_id = %s WHERE telegram_id = %s", (file_id, user_id))
    conn.commit()

    await message.answer("📥 تم استلام لقطة الشاشة! سيتم التحقق يدويًا من الدفع قريبًا ✅")


if __name__ == '__main__':
    print("✅ البوت قيد التشغيل ...")
    executor.start_polling(dp, skip_updates=True)
