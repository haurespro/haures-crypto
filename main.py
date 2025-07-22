import logging
import os
import asyncio
import sys
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncpg

# If testing locally, you might want to use python-dotenv
# from dotenv import load_dotenv
# load_dotenv() # This will load variables from .env file

# Configure logging to provide detailed information
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Environment Variables ---
# Fetch sensitive information from environment variables for security
API_TOKEN = os.getenv("BOT_TOKEN")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

# Crucial check: Exit if BOT_TOKEN is not set, as the bot cannot function without it.
# We keep this as it's a fundamental requirement.
if not API_TOKEN:
    logger.critical("BOT_TOKEN environment variable is NOT SET. Please set it in Render.")
    sys.exit("Critical Error: BOT_TOKEN is missing. Exiting application.")

# --- Bot and Dispatcher Setup ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Global variable for database connection pool
db_pool = None

async def create_db_pool():
    """
    Establishes and returns a PostgreSQL database connection pool using asyncpg.
    Ensures all necessary DB environment variables are set.
    """
    # Changed to logger.error instead of sys.exit to allow bot to potentially start
    # if DB is not immediately critical for a simple bot, but for your use case,
    # DB is critical, so we will still exit if variables are missing.
    if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_HOST]):
        logger.critical("One or more database environment variables (DB_USER, DB_PASSWORD, DB_NAME, DB_HOST) are NOT SET! Please check Render settings.")
        sys.exit("Critical Error: Missing critical database environment variables. Cannot connect to DB. Exiting application.") # Still exit here

    try:
        pool = await asyncpg.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            min_size=1,
            max_size=10,
            timeout=30 # Add a timeout for connection attempts
        )
        logger.info("Database connection pool created successfully.")
        return pool
    except Exception as e:
        logger.critical(f"Failed to create database pool: {e}", exc_info=True)
        # We will not sys.exit here, instead main() will check if db_pool is None
        return None # Return None if pool creation fails

async def init_db():
    """
    Creates the 'users' table if it does not already exist.
    Ensures a unique constraint on 'telegram_id'.
    Updated to include new fields: password, age, experience, capital.
    """
    if db_pool is None:
        logger.error("Cannot initialize database: DB pool is not available.")
        return False # Indicate failure

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
        return True # Indicate success
    except Exception as e:
        logger.critical(f"Failed to initialize database table 'users': {e}", exc_info=True)
        # We will not sys.exit here, main() will handle it
        return False # Indicate failure

# --- FSM States ---
class UserData(StatesGroup):
    """
    States for the Finite State Machine (FSM) to manage user input flow.
    Updated to include new states.
    """
    waiting_email = State()
    waiting_password = State()
    waiting_age = State()
    waiting_experience = State()
    waiting_capital = State()
    waiting_payment = State()

# --- Handlers ---

@dp.message(F.command("start"))
async def send_welcome(message: types.Message, state: FSMContext):
    """
    Handles the /start command. Responds with a welcome message including
    user info and prompts for email.
    """
    await state.clear() # Clear any previous state for a fresh start
    user_id = message.from_user.id
    username = message.from_user.username if message.from_user.username else "لا يوجد اسم مستخدم"
    full_name = message.from_user.full_name

    logger.info(f"User {user_id} ({full_name} @{username}) sent /start. Initiating flow.")

    welcome_message = (
        f"👋 مرحباً بك يا {full_name} (@{username})!\n"
        f"أنا بوت Haures، دليلك لأفضل برنامج في التجارة الإلكترونية.\n"
        "📩 الرجاء أدخل بريدك الإلكتروني لتبدأ رحلتك معنا:"
    )
    await message.answer(welcome_message)
    await state.set_state(UserData.waiting_email)

@dp.message(UserData.waiting_email, F.text)
async def process_email(message: types.Message, state: FSMContext):
    """
    Handles the user's email input. Validates the email and moves to the next state.
    """
    email = message.text
    # Basic email validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        await message.reply("❌ هذا ليس بريدًا إلكترونيًا صالحًا. الرجاء إدخال بريد إلكتروني صحيح:")
        return # Stay in the same state

    await state.update_data(email=email) # Store the email
    logger.info(f"User {message.from_user.id} provided email: {email}")
    await message.answer("✅ تم استلام بريدك الإلكتروني بنجاح.\nالرجاء أدخل كلمة مرور:")
    await state.set_state(UserData.waiting_password) # Move to the next state

@dp.message(UserData.waiting_password, F.text)
async def process_password(message: types.Message, state: FSMContext):
    """
    Handles the user's password input. Stores it and moves to the next state.
    (يمكنك إضافة تحقق أقوى لكلمة المرور هنا)
    """
    password = message.text
    if len(password) < 6: # مثال على تحقق بسيط
        await message.reply("كلمة المرور قصيرة جدًا. يجب أن تكون 6 أحرف على الأقل:")
        return

    await state.update_data(password=password)
    logger.info(f"User {message.from_user.id} provided password.")
    await message.answer("✅ تم استلام كلمة المرور.\nالرجاء أدخل عمرك (رقم):")
    await state.set_state(UserData.waiting_age)

@dp.message(UserData.waiting_age, F.text)
async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if not (0 < age < 100): # تحقق بسيط للعمر المنطقي
            await message.reply("❌ الرجاء إدخال عمر صالح (رقم بين 1 و 99):")
            return
        await state.update_data(age=age)
        logger.info(f"User {message.from_user.id} provided age: {age}")
        await message.answer("✅ تم استلام العمر.\nالرجاء أدخل مستوى خبرتك في التجارة الإلكترونية:")
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
    await message.answer("✅ تم استلام مستوى الخبرة.\nالرجاء أدخل رأس المال الذي تنوي البدء به:")
    await state.set_state(UserData.waiting_capital)

@dp.message(UserData.waiting_capital, F.text)
async def process_capital(message: types.Message, state: FSMContext):
    capital = message.text
    if not capital.strip():
        await message.reply("❌ الرجاء إدخال رأس المال:")
        return
    await state.update_data(capital=capital)
    logger.info(f"User {message.from_user.id} provided capital.")
    await message.answer("✅ تم استلام رأس المال.\nالرجاء إرسال صورة إيصال الدفع:")
    await state.set_state(UserData.waiting_payment)

@dp.message(UserData.waiting_payment, F.photo)
async def process_payment_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id # الحصول على أكبر حجم للصورة
    await state.update_data(payment_image=photo_id)
    logger.info(f"User {message.from_user.id} provided payment image: {photo_id}")
    await message.answer("✅ تم استلام صورة الدفع بنجاح!")

    # هنا يمكنك حفظ جميع البيانات في قاعدة البيانات
    user_data = await state.get_data()
    telegram_id = message.from_user.id
    email = user_data.get('email')
    password = user_data.get('password')
    age = user_data.get('age')
    experience = user_data.get('experience')
    capital = user_data.get('capital')
    payment_image = user_data.get('payment_image')

    # Ensure db_pool is available before trying to insert
    if db_pool is None:
        logger.error(f"Cannot save user {telegram_id} data: DB pool is not available.")
        await message.answer("❌ لا يمكن حفظ بياناتك الآن بسبب مشكلة في قاعدة البيانات. الرجاء المحاولة لاحقاً.")
        await state.clear()
        return

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
            ''', telegram_id, email, password, age, experience, capital, payment_image)
        logger.info(f"User {telegram_id} data saved/updated successfully in DB.")
        await message.answer("🎉 تم تسجيل بياناتك بنجاح! شكراً لك.")
    except Exception as e:
        logger.error(f"Failed to save user {telegram_id} data to DB: {e}", exc_info=True)
        await message.answer("❌ حدث خطأ أثناء حفظ بياناتك. الرجاء المحاولة مرة أخرى لاحقاً.")

    await state.clear() # مسح الحالة بعد اكتمال العملية

# --- Main function to run the bot ---
async def main():
    global db_pool
    # Try to create DB pool
    db_pool = await create_db_pool()

    # If DB pool creation failed, log and exit, as DB is critical for this bot.
    if db_pool is None:
        logger.critical("Failed to initialize database pool. Bot cannot start without a database connection.")
        sys.exit("Critical Error: Database connection failed. Exiting application.")

    # Try to initialize DB tables
    db_initialized = await init_db()
    if not db_initialized:
        logger.critical("Failed to initialize database tables. Bot cannot start.")
        if db_pool:
            await db_pool.close() # Close pool here too if initialization fails after creation
        sys.exit("Critical Error: Database table initialization failed. Exiting application.")

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot) # Start listening for updates from Telegram
    except Exception as e:
        logger.critical(f"Bot polling stopped due to an unhandled error: {e}", exc_info=True)
    finally:
        # Close the DB pool within the same event loop context
        if db_pool:
            logger.info("Closing database connection pool.")
            await db_pool.close() # Direct await call, NOT asyncio.run()
        logger.info("Bot polling stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"An unhandled error occurred in main execution: {e}", exc_info=True)
    # The 'finally' block that caused the error has been removed from here
    
