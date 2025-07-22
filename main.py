import logging
import os
import asyncio
import sys

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncpg

# إعداد السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- المتغيرات ---
API_TOKEN = os.getenv("BOT_TOKEN")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

if not API_TOKEN:
    logger.critical("BOT_TOKEN غير موجود. تأكد من وضعه في Render.")
    sys.exit("BOT_TOKEN مفقود. تم إيقاف التشغيل.")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db_pool = None

# الاتصال بقاعدة البيانات
async def create_db_pool():
    global db_pool
    if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_HOST]):
        logger.critical("معلومات الاتصال بقاعدة البيانات ناقصة.")
        raise ValueError("معلومات DB ناقصة.")
    db_pool = await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST
    )
    logger.info("✅ تم إنشاء الاتصال بقاعدة البيانات.")

async def init_db():
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE,
                full_name TEXT,
                email TEXT,
                code TEXT,
                payment_image TEXT
            );
        ''')
        logger.info("✅ تم التأكد من وجود جدول users.")

# الحالة FSM
class UserData(StatesGroup):
    waiting_email = State()
    waiting_code = State()
    waiting_payment = State()

# /start
@dp.message(F.command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    user = message.from_user
    welcome_text = (
        f"👋 أهلاً {user.full_name}!\n\n"
        "📦 مرحباً بك في *Haures Bot* — أقوى نظام ذكي للتجارة الإلكترونية باستخدام USDT عبر شبكة TRC20 💰\n\n"
        "🚀 سيساعدك هذا البوت على إرسال معلوماتك والدفع بكل سهولة وأمان.\n"
        "🔐 لنبدأ، من فضلك أدخل بريدك الإلكتروني:"
    )
    await message.answer(welcome_text, parse_mode="Markdown")
    await state.set_state(UserData.waiting_email)

# البريد
@dp.message(UserData.waiting_email)
async def email_handler(message: types.Message, state: FSMContext):
    if "@" not in message.text or "." not in message.text:
        await message.answer("❌ البريد الإلكتروني غير صالح. حاول مرة أخرى:")
        return
    await state.update_data(email=message.text)
    await message.answer("✅ أدخل الرمز السري (على الأقل 8 أحرف أو أرقام):")
    await state.set_state(UserData.waiting_code)

# الكود السري
@dp.message(UserData.waiting_code)
async def code_handler(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if len(code) < 8:
        await message.answer("❌ الرمز قصير جداً. يجب أن يكون 8 أحرف أو أرقام على الأقل.")
        return
    await state.update_data(code=code)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 نسخ عنوان الدفع", callback_data="copy_address")]
    ])
    await message.answer(
        "💳 أرسل المبلغ إلى العنوان التالي:\n`TLxUzr....TRC20`",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await message.answer("📷 الآن، أرسل لقطة شاشة لإثبات الدفع:")
    await state.set_state(UserData.waiting_payment)

# إثبات الدفع
@dp.message(F.photo, UserData.waiting_payment)
async def payment_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.photo[-1].file_id

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", message.from_user.id)
        if user:
            await conn.execute('''
                UPDATE users
                SET email = $2, code = $3, payment_image = $4
                WHERE telegram_id = $1
            ''', message.from_user.id, data["email"], data["code"], file_id)
        else:
            await conn.execute('''
                INSERT INTO users (telegram_id, full_name, email, code, payment_image)
                VALUES ($1, $2, $3, $4, $5)
            ''', message.from_user.id, message.from_user.full_name, data["email"], data["code"], file_id)
    await message.answer("✅ تم استلام معلوماتك بنجاح! سيتم التحقق من الدفع قريبًا. شكراً لاستخدامك Haures 💼")
    await state.clear()

# بدء البوت
async def main():
    await create_db_pool()
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("تم إيقاف البوت.")
