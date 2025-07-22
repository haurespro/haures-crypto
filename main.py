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
    # *** التعديل هنا: تأكد من إغلاق القوس المربع والقوس الدائري ***
    if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_HOST]): # هذا السطر تم تصحيحه
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
        
