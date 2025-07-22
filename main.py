import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor  # هذا هو التغيير الرئيسي هنا!
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import asyncpg # تأكد من أن هذا المستورد موجود

# قم بتعيين مستوى التسجيل
logging.basicConfig(level=logging.INFO)

# متغيرات البيئة (سيتم سحبها من Render)
API_TOKEN = os.getenv("BOT_TOKEN")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

# إعداد البوت والديسباتشر
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage()) # تم نقل تعريف التخزين هنا ليكون في مكان واحد

# تهيئة تجمع الاتصال بقاعدة البيانات
db_pool = None

async def create_db_pool():
    # التحقق من أن جميع متغيرات قاعدة البيانات موجودة قبل محاولة الاتصال
    if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_HOST]):
        logging.error("Database environment variables are not fully set!")
        raise ValueError("Missing database environment variables.")
    return await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST
    )

# إنشاء الجدول إذا لم يكن موجوداً
async def init_db():
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                email TEXT,
                code TEXT,
                payment_image TEXT
            );
        ''')
    logging.info("Database table 'users' checked/created successfully.")


# FSM - تعريف الحالات
class UserData(StatesGroup):
    waiting_email = State()
    waiting_code = State()
    waiting_payment = State()

# بداية المحادثة
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer("👋 مرحباً بك!\nأدخل بريدك الإلكتروني:")
    await UserData.waiting_email.set()

# البريد الإلكتروني
@dp.message_handler(state=UserData.waiting_email)
async def process_email(message: types.Message, state: FSMContext):
    await state.update_data(email=message.text)
    await message.answer("✅ أدخل الرمز السري:")
    await UserData.waiting_code.set()

# الرمز السري
@dp.message_handler(state=UserData.waiting_code)
async def process_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📋 نسخ عنوان الدفع", callback_data="copy")
    )
    await message.answer("💳 أرسل المبلغ إلى هذا العنوان:\n`TLxUzr...TRC20`", parse_mode="Markdown", reply_markup=keyboard)
    await message.answer("📷 أرسل لقطة الشاشة كدليل على الدفع:")
    await UserData.waiting_payment.set()

# لقطة الشاشة
@dp.message_handler(content_types=types.ContentType.PHOTO, state=UserData.waiting_payment)
async def process_payment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.photo[-1].file_id

    try:
        async with db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (telegram_id, email, code, payment_image)
                VALUES ($1, $2, $3, $4)
            ''', message.from_user.id, data['email'], data['code'], file_id)
        await message.answer("✅ تم استلام الدفعة. سيتم التحقق يدوياً. شكراً!")
    except Exception as e:
        logging.error(f"Error inserting data into DB: {e}")
        await message.answer("❌ حدث خطأ أثناء حفظ معلوماتك. الرجاء المحاولة مرة أخرى.")
    finally:
        await state.finish()

# زر النسخ (لا ينسخ فعلياً لأنه تيليجرام لا يدعم)
@dp.callback_query_handler(lambda c: c.data == 'copy')
async def copy_address(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id, text="📋 تم نسخ العنوان (انسخه يدوياً)")

# دالة التشغيل عند بدء البوت
async def on_startup(dispatcher):
    global db_pool
    db_pool = await create_db_pool()
    await init_db()
    logging.info("✅ البوت جاهز للعمل...")

# تشغيل البوت
if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True) # skip_updates لتجاهل التحديثات القديمة
