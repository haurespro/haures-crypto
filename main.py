import logging
import os
import asyncio
import sys # Import sys for sys.exit
import re # Added for email validation

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncpg

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
    if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_HOST]):
        logger.critical("One or more database environment variables (DB_USER, DB_PASSWORD, DB_NAME, DB_HOST) are NOT SET! Please check Render settings.")
        # Instead of raising ValueError, raise a more specific error or sys.exit
        sys.exit("Critical Error: Missing critical database environment variables. Cannot connect to DB. Exiting application.")
    try:
        pool = await asyncpg.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            min_size=1, 
            max_size=10
        )
        logger.info("Database connection pool created successfully.")
        return pool
    except Exception as e:
        logger.critical(f"Failed to create database pool: {e}", exc_info=True)
        # It's better to exit here if DB connection is critical for bot function
        sys.exit(f"Critical Error: Failed to create database pool: {e}") 

async def init_db():
    """
    Creates the 'users' table if it does not already exist.
    Ensures a unique constraint on 'telegram_id'.
    Updated to include new fields: password, age, experience, capital.
    """
    try:
        async with db_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE, 
                    email TEXT,
                    password TEXT, -- Added for password
                    age INT,        -- Added for age
                    experience TEXT,-- Added for experience
                    capital TEXT,   -- Added for capital
                    payment_image TEXT
                );
            ''')
        logger.info("Database table 'users' checked/created successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database table 'users': {e}", exc_info=True)
        # Exit if table creation fails, as bot won't function
        sys.exit(f"Critical Error: Failed to initialize database table: {e}")

# --- FSM States ---
class UserData(StatesGroup):
    """
    States for the Finite State Machine (FSM) to manage user input flow.
    Updated to include new states.
    """
    waiting_email = State()
    waiting_password = State() # New state
    waiting_age = State()      # New state
    waiting_experience = State() # New state
    waiting_capital = State()    # New state
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

@dp.message(UserData.waiting_email)
async def process_email(message: types.Message, state: FSMContext):
    """
    Processes the user's email input. Performs basic validation.
    Prompts for secret code and sets the state to waiting_password.
    """
    email = message.text
    if not email or not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): # Added check for empty message
        logger.warning(f"User {message.from_user.id} entered invalid email: {email}")
        await message.answer("❌ البريد الإلكتروني غير صالح. حاول مرة أخرى:")
        return

    await state.update_data(email=email)
    logger.info(f"User {message.from_user.id} entered email: {email}. Prompting for password.")
    await message.answer("🔑 الرجاء إدخال الرمز السري (8 أحرف أو أكثر):")
    await state.set_state(UserData.waiting_password) # Advance to waiting_password

@dp.message(UserData.waiting_password)
async def process_password(message: types.Message, state: FSMContext):
    """
    Processes the user's secret code input. Validates password length.
    Prompts for age and sets the state to waiting_age.
    """
    password = message.text
    if not password or len(password) < 8: # Added check for empty message
        logger.warning(f"User {message.from_user.id} entered short or empty password.")
        await message.answer("❌ الرمز السري قصير جدًا. يجب أن يكون 8 أحرف أو أكثر:")
        return

    await state.update_data(password=password)
    logger.info(f"User {message.from_user.id} entered password. Prompting for age.")
    await message.answer("📊 كم عمرك؟")
    await state.set_state(UserData.waiting_age) # Advance to waiting_age

@dp.message(UserData.waiting_age)
async def process_age(message: types.Message, state: FSMContext):
    """
    Processes the user's age input. Validates age and prompts for experience or ends flow.
    """
    try:
        age_text = message.text
        if not age_text: # Check if message is empty
            logger.warning(f"User {message.from_user.id} sent empty message for age.")
            await message.answer("❌ الرجاء إدخال عمر صحيح (رقم فقط):")
            return

        age = int(age_text)
        if age < 18:
            logger.warning(f"User {message.from_user.id} entered age below 18: {age}. Ending flow.")
            await message.answer("⚠️ عذرًا، يجب أن يكون عمرك 18 سنة أو أكثر للمشاركة.\nروح تقرا بابا 📚!")
            await state.clear() # Clear state and end conversation
            return
        
        await state.update_data(age=age)
        logger.info(f"User {message.from_user.id} entered age: {age}. Prompting for experience.")
        await message.answer("🧠 هل كانت لديك خبرة في مجال التجارة الإلكترونية؟ (نعم/لا)")
        await state.set_state(UserData.waiting_experience) # Advance to waiting_experience
    except ValueError:
        logger.warning(f"User {message.from_user.id} entered non-numeric age: {message.text}")
        await message.answer("❌ الرجاء إدخال عمر صحيح (رقم فقط):")

@dp.message(UserData.waiting_experience)
async def process_experience(message: types.Message, state: FSMContext):
    """
    Processes user's experience input. Prompts for capital.
    """
    if not message.text: # Ensure there's text input
        logger.warning(f"User {message.from_user.id} sent empty message for experience.")
        await message.answer("❌ الرجاء الإجابة بنعم أو لا.")
        return

    await state.update_data(experience=message.text)
    logger.info(f"User {message.from_user.id} entered experience: {message.text}. Prompting for capital.")
    await message.answer("💰 هل لديك رأس مال صغير لكي تبدأ التجارة الإلكترونية؟ (نعم/لا)")
    await state.set_state(UserData.waiting_capital) # Advance to waiting_capital

@dp.message(UserData.waiting_capital)
async def process_capital(message: types.Message, state: FSMContext):
    """
    Processes user's capital input. Provides payment address and prompts for screenshot.
    """
    if not message.text: # Ensure there's text input
        logger.warning(f"User {message.from_user.id} sent empty message for capital.")
        await message.answer("❌ الرجاء الإجابة بنعم أو لا.")
        return

    await state.update_data(
    
