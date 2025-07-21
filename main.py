import logging
import re
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InputFile
import asyncpg
import os

API_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
USDT_ADDRESS = "TVaabc1234xyz567"  # عنوان TRC20

# إعدادات اللوغ
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# اتصال بالقاعدة
async def connect_db():
    return await asyncpg.connect(DATABASE_URL)

# تحقق من صحة البريد الإلكتروني
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+.[^@]+", email)

# تحقق من الرمز السري
def is_valid_password(pwd):
    return len(pwd) >= 8 and re.search(r'[A-Za-z]', pwd) and re.search(r'[0-9]', pwd)

# رسالة البداية
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer(
        "🎓 مرحبًا بك في *برنامج Haures التعليمي المجاني*

"
        "🚀 *Haures* هو أفضل برنامج في التجارة الإلكترونية، مجاني تمامًا، فقط تحتاج لدفع مساهمة رمزية (2 USDT) لمساعدتنا على التطوير وجلب برامج أقوى.

"
        "💬 *The best e-commerce learning program (Haures)* is free! A small fee of 2 USDT helps us build more tools.
"
        "
✅ هل أنت مستعد؟ أرسل بريدك الإلكتروني."
    )

# استقبال البريد الإلكتروني
@dp.message_handler(lambda msg: '@' in msg.text)
async def process_email(message: types.Message):
    email = message.text.strip()
    if not is_valid_email(email):
        await message.reply("❌ البريد الإلكتروني غير صالح. أعد المحاولة.")
        return
    await message.reply("✅ جيد! أرسل الآن رمزًا سريًا (8 خانات على الأقل، يحتوي على أرقام وحروف).")
    await save_data(user_id=message.from_user.id, email=email)

# استقبال الرمز السري
@dp.message_handler(lambda msg: len(msg.text.strip()) >= 8)
async def process_password(message: types.Message):
    password = message.text.strip()
    if not is_valid_password(password):
        await message.reply("❌ الرمز السري غير صالح. يجب أن يحتوي على أرقام وحروف.")
        return
    await update_password(user_id=message.from_user.id, password=password)
    await message.reply(
        f"✅ ممتاز! الآن، يرجى دفع 2 USDT إلى العنوان التالي:

"
        f"`{USDT_ADDRESS}`

"
        "📌 شبكة TRC20 فقط!
"
        "ثم أرسل لقطة شاشة تثبت الدفع هنا."
    )

# استقبال لقطة الشاشة
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def process_screenshot(message: types.Message):
    photo = message.photo[-1]
    file_id = photo.file_id
    await update_payment(message.from_user.id, file_id)
    await message.reply("📥 تم استلام لقطة الشاشة. سيتم التحقق يدويًا من الدفع قريبًا. ✅")

# الشروط
@dp.message_handler(commands=['rules'])
async def show_rules(message: types.Message):
    await message.reply(
        "📜 *شروط الانضمام لبرنامج Haures:*
"
        "1. توفير الوقت للتعلم
"
        "2. تقبل طريقة تفكير منطقية مبنية على دراسات
"
        "3. احترام متبادل
"
        "4. الرد على رسائل الخبراء
"
        "5. عدم الفشل من المحاولة الأولى
"
        "6. تقبل التحديث المستمر

"
        "*Rules of Haures Program:*
"
        "1. Dedicate time to learn
"
        "2. Accept logic-based thinking
"
        "3. Show mutual respect
"
        "4. Respond to mentors
"
        "5. Don’t fear first-time failure
"
        "6. Be open to updates"
    )

# دوال القاعدة
async def save_data(user_id, email):
    conn = await connect_db()
    await conn.execute("INSERT INTO haures_users (user_id, email) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING", user_id, email)
    await conn.close()

async def update_password(user_id, password):
    conn = await connect_db()
    await conn.execute("UPDATE haures_users SET password=$1 WHERE user_id=$2", password, user_id)
    await conn.close()

async def update_payment(user_id, file_id):
    conn = await connect_db()
    await conn.execute("UPDATE haures_users SET payment_screenshot=$1 WHERE user_id=$2", file_id, user_id)
    await conn.close()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
