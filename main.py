import logging
import os
import asyncio
import sys
import re
from threading import Thread # هام للحفاظ على نشاط Replit

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncpg
from flask import Flask # هام للحفاظ على نشاط Replit

# --- إعداد التسجيل (Logging) ---
# سيسجل البوت كل الأحداث الهامة هنا
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- متغيرات البيئة (Environment Variables) ---
# تُجلب المعلومات الحساسة من متغيرات البيئة (Secrets في Replit) للأمان
API_TOKEN = os.getenv("BOT_TOKEN")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

# تحقق حاسم: إذا لم يتم تعيين توكن البوت، لا يمكن للبوت العمل
if not API_TOKEN:
    logger.critical("BOT_TOKEN environment variable is NOT SET. Please set it in your Replit secrets.")
    sys.exit("Critical Error: BOT_TOKEN is missing. Exiting application.")

# --- تطبيق Flask للحفاظ على نشاط Replit ---
app = Flask(__name__)

@app.route('/')
def index():
    """
    مسار ويب بسيط للحفاظ على نشاط Replit.
    """
    return "Bot is alive and running!"

def run_flask_app():
    """
    يشغل خادم ويب Flask في خيط منفصل.
    Replit يوفر منفذًا (PORT) في متغير البيئة.
    """
    port = int(os.environ.get('PORT', 8080)) # المنفذ الافتراضي 8080 إذا لم يتم تعيينه بواسطة Replit
    logger.info(f"Starting Flask web server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    """
    يبدأ خادم ويب Flask في خيط في الخلفية.
    """
    t = Thread(target=run_flask_app)
    t.start()

# --- إعداد البوت و Dispatcher ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# متغير عام لمجموعة اتصالات قاعدة البيانات
db_pool = None

async def create_db_pool():
    """
    يُنشئ ويعيد مجموعة اتصالات قاعدة بيانات PostgreSQL باستخدام asyncpg.
    يتأكد من تعيين جميع متغيرات البيئة الضرورية لقاعدة البيانات.
    """
    if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_HOST]):
        logger.critical("One or more database environment variables (DB_USER, DB_PASSWORD, DB_NAME, DB_HOST) are NOT SET! Please check your Replit secrets.")
        sys.exit("Critical Error: Missing critical database environment variables. Cannot connect to DB. Exiting application.")

    try:
        pool = await asyncpg.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            min_size=1,
            max_size=10,
            timeout=30
        )
        logger.info("Database connection pool created successfully.")
        return pool
    except Exception as e:
        logger.critical(f"Failed to create database pool: {e}", exc_info=True)
        sys.exit(f"Critical Error: Failed to create database pool: {e}") # الخروج إذا فشل الاتصال بقاعدة البيانات

async def init_db():
    """
    يُنشئ جدول 'users' إذا لم يكن موجودًا بالفعل.
    """
    if db_pool is None:
        logger.error("Cannot initialize database: DB pool is not available.")
        return False

    try:
        async with db_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE,
                    email TEXT,
                    password TEXT,
                    age INT,
                    experience TEXT,
                    capital TEXT,
                    payment_image TEXT
                );
            ''')
        logger.info("Database table 'users' checked/created successfully.")
        return True
    except Exception as e:
        logger.critical(f"Failed to initialize database table 'users': {e}", exc_info=True)
        return False

# --- حالات FSM (مدير حالات Finite State Machine) ---
class UserData(StatesGroup):
    waiting_email = State()
    waiting_password = State()
    waiting_age = State()
    waiting_experience = State()
    waiting_capital = State()
    waiting_payment = State()
    registered = State()

# --- المعالجات (Handlers) ---

# **المعالجة لأمر /start - تم التعديل لاستخدام commands=["start"]**
@dp.message(commands=["start"])
async def send_welcome(message: types.Message, state: FSMContext):
    await state.clear() # مسح أي حالة سابقة للمستخدم
    user_id = message.from_user.id
    username = message.from_user.username if message.from_user.username else "لا يوجد اسم مستخدم"
    full_name = message.from_user.full_name

    logger.info(f"User {user_id} ({full_name} @{username}) sent /start. Initiating flow.")

    welcome_message = (
        f"👋 مرحباً بك يا {full_name} (@{username})!
"
        f"أنا بوت Haures، دليلك لأفضل برنامج في التجارة الإلكترونية.
"
        "📩 الرجاء أدخل بريدك الإلكتروني لتبدأ رحلتك معنا:"
    )
    await message.answer(welcome_message)
    await state.set_state(UserData.waiting_email)

@dp.message(UserData.waiting_email, F.text)
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    if not re.match(r"[^@]+@[^@]+.[^@]+", email):
        await message.reply("❌ هذا ليس بريدًا إلكترونيًا صالحًا. الرجاء إدخال بريد إلكتروني صحيح:")
        return

    await state.update_data(email=email)
    logger.info(f"User {message.from_user.id} provided email: {email}")
    await message.answer("✅ تم استلام بريدك الإلكتروني بنجاح.
الرجاء أدخل كلمة مرور:")
    await state.set_state(UserData.waiting_password)

@dp.message(UserData.waiting_password, F.text)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    if len(password) < 6:
        await message.reply("كلمة المرور قصيرة جدًا. يجب أن تكون 6 أحرف على الأقل:")
        return

    await state.update_data(password=password)
    logger.info(f"User {message.from_user.id} provided password.")
    await message.answer("✅ تم استلام كلمة المرور.
الرجاء أدخل عمرك (رقم):")
    await state.set_state(UserData.waiting_age)

@dp.message(UserData.waiting_age, F.text)
async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if not (0 < age < 100):
            await message.reply("❌ الرجاء إدخال عمر صالح (رقم بين 1 و 99):")
            return
        await state.update_data(age=age)
        logger.info(f"User {message.from_user.id} provided age: {age}")
        await message.answer("✅ تم استلام العمر.
الرجاء أدخل مستوى خبرتك في التجارة الإلكترونية:")
        await state.set_state(UserData.waiting_experience)
    except ValueError:
        await message.reply("❌ الرجاء إدخال رقم صحيح لعمرك:")

@dp.message(UserData.waiting_experience, F.text)
async def process_experience(message: types.Message, state: FSMContext):
    experience = message.text
    if not experience.strip():
        await message.reply("❌ الرجاء وصف مستوى خبرتك:")
        return
    await state.update_data(experience=experience)
    logger.info(f"User {message.from_user.id} provided experience.")
    await message.answer("✅ تم استلام مستوى الخبرة.
الرجاء أدخل رأس المال الذي تنوي البدء به:")
    await state.set_state(UserData.waiting_capital)

@dp.message(UserData.waiting_capital, F.text)
async def process_capital(message: types.Message, state: FSMContext):
    capital = message.text
    if not capital.strip():
        await message.reply("❌ الرجاء إدخال رأس المال:")
        return

    await state.update_data(capital=capital)
    logger.info(f"User {message.from_user.id} provided capital: {capital}")
    await message.answer("✅ تم استلام رأس المال.
الآن، الرجاء إرسال صورة إثبات الدفع:")
    await state.set_state(UserData.waiting_payment)

@dp.message(UserData.waiting_payment, F.photo)
async def process_payment_photo(message: types.Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await state.update_data(payment_image=photo_file_id)
    logger.info(f"User {message.from_user.id} uploaded payment photo with file_id: {photo_file_id}")

    user_data = await state.get_data()
    telegram_id = message.from_user.id

    try:
        async with db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (telegram_id, email, password, age, experience, capital, payment_image)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (telegram_id) DO UPDATE
                SET email = EXCLUDED.email,
                    password = EXCLUDED.password,
                    age = EXCLUDED.age,
                    experience = EXCLUDED.experience,
                    capital = EXCLUDED.capital,
                    payment_image = EXCLUDED.payment_image;
            ''',
            telegram_id,
            user_data['email'],
            user_data['password'],
            user_data['age'],
            user_data['experience'],
            user_data['capital'],
            user_data['payment_image']
            )
        logger.info(f"User {telegram_id} data saved/updated in database.")
        await message.answer(
            "🎉 شكرًا لك! تم تسجيل جميع معلوماتك بنجاح.
"
            "سنتواصل معك قريباً لتقديم الدخول إلى برنامجنا."
        )
        await state.set_state(UserData.registered)
        await state.clear()
    except Exception as e:
        logger.error(f"Failed to save user {telegram_id} data to DB: {e}", exc_info=True)
        await message.answer("❌ عذرًا، حدث خطأ أثناء حفظ معلوماتك. الرجاء حاول مرة أخرى لاحقًا.")
        await state.clear()

@dp.message(UserData.waiting_payment, ~F.photo)
async def process_payment_invalid(message: types.Message):
    await message.reply("❌ الرجاء إرسال صورة لإثبات الدفع، وليس نصاً أو أي نوع آخر من الملفات.")

# --- دالة main لتشغيل البوت ---
async def main():
    global db_pool
    logger.info("Starting bot initialization...")

    # بدء خادم ويب Flask في خيط منفصل للحفاظ على نشاط Replit
    keep_alive()
    logger.info("Flask web server for keep-alive started.")

    # إنشاء مجموعة اتصالات قاعدة البيانات
    db_pool = await create_db_pool()
    if db_pool is None:
        logger.critical("Failed to acquire database pool. Exiting application.")
        sys.exit("Critical Error: Database pool not available.")

    # تهيئة جداول قاعدة البيانات
    if not await init_db():
        logger.critical("Failed to initialize database tables. Exiting application.")
        sys.exit("Critical Error: Database tables could not be set up.")

    logger.info("Database setup complete. Starting polling...")
    # بدء تشغيل البوت (باستخدام Long Polling)
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Bot polling failed: {e}", exc_info=True)
    finally:
        # التأكد من إغلاق مجموعة اتصالات قاعدة البيانات عند توقف البوت
        if db_pool:
            await db_pool.close()
            logger.info("Database connection pool closed.")

# نقطة الدخول الرئيسية للسكريبت
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main execution: {e}", exc_info=True)

