import logging
import os
import asyncio
import sys # Import sys for sys.exit

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
# Initialize the Bot with the API token
bot = Bot(token=API_TOKEN)
# Initialize the Dispatcher with MemoryStorage for FSM
# In aiogram v3.x, the bot instance is passed to start_polling, not Dispatcher.__init__()
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
        raise ValueError("Missing critical database environment variables. Cannot connect to DB.")
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
        raise 

async def init_db():
    """
    Creates the 'users' table in the database if it does not already exist.
    Ensures a unique constraint on 'telegram_id'.
    """
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE, 
                email TEXT,
                code TEXT,
                payment_image TEXT
            );
        ''')
    logger.info("Database table 'users' checked/created successfully.")

# --- FSM States ---
class UserData(StatesGroup):
    """
    States for the Finite State Machine (FSM) to manage user input flow.
    """
    waiting_email = State()
    waiting_code = State()
    waiting_payment = State()

# --- Handlers ---

# IMPORTANT: This /start handler is placed first and uses F.command("start") for explicit priority.
@dp.message(F.command("start")) 
async def send_welcome(message: types.Message, state: FSMContext):
    """
    Handles the /start command. Responds with a welcome message and prompts for email.
    Sets the state to waiting_email.
    """
    logger.info(f"User {message.from_user.id} ({message.from_user.full_name}) sent /start. Initiating flow.")
    await message.answer("👋 مرحباً بك!\nأدخل بريدك الإلكتروني:")
    await state.set_state(UserData.waiting_email)

# Handler for user's email input
@dp.message(UserData.waiting_email)
async def process_email(message: types.Message, state: FSMContext):
    """
    Processes the user's email input. Performs basic validation.
    Prompts for secret code and sets the state to waiting_code.
    """
    if not message.text or "@" not in message.text or "." not in message.text:
        logger.warning(f"User {message.from_user.id} entered invalid email: {message.text}")
        await message.answer("❌ يرجى إدخال بريد إلكتروني صالح.")
        return

    await state.update_data(email=message.text)
    logger.info(f"User {message.from_user.id} entered email: {message.text}. Prompting for code.")
    await message.answer("✅ أدخل الرمز السري:")
    await state.set_state(UserData.waiting_code)

# Handler for user's secret code input
@dp.message(UserData.waiting_code)
async def process_code(message: types.Message, state: FSMContext):
    """
    Processes the user's secret code input.
    Provides payment address and prompts for payment screenshot.
    Sets the state to waiting_payment.
    """
    if not message.text: 
        await message.answer("❌ يرجى إدخال رمز صالح.")
        return

    await state.update_data(code=message.text)
    logger.info(f"User {message.from_user.id} entered code. Prompting for payment.")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📋 نسخ عنوان الدفع", callback_data="copy_address")
    ]])
    await message.answer(
        "💳 أرسل المبلغ إلى هذا العنوان:\n`TLxUzr...TRC20`", 
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await message.answer("📷 أرسل لقطة الشاشة كدليل على الدفع:")
    await state.set_state(UserData.waiting_payment)

# Handler for user's payment screenshot
@dp.message(F.photo, UserData.waiting_payment) 
async def process_payment(message: types.Message, state: FSMContext):
    """
    Processes the payment screenshot provided by the user.
    Saves or updates user data (Telegram ID, email, code, payment image file ID) in the database.
    Clears the FSM state upon completion.
    """
    data = await state.get_data()
    file_id = message.photo[-1].file_id 

    try:
        async with db_pool.acquire() as conn:
            existing_user = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1", message.from_user.id
            )
            if existing_user:
                await conn.execute('''
                    UPDATE users
                    SET email = $2, code = $3, payment_image = $4
                    WHERE telegram_id = $1
                ''', message.from_user.id, data.get('email'), data.get('code'), file_id)
                logger.info(f"User {message.from_user.id} updated their payment details. Telegram File ID: {file_id}")
                await message.answer("✅ تم تحديث بيانات دفعتك. سيتم التحقق يدوياً. شكراً!")
            else:
                await conn.execute('''
                    INSERT INTO users (telegram_id, email, code, payment_image)
                    VALUES ($1, $2, $3, $4)
                ''', message.from_user.id, data.get('email'), data.get('code'), file_id)
                logger.info(f"User {message.from_user.id} data saved successfully. Telegram File ID: {file_id}")
                await message.answer("✅ تم استلام دف
                
