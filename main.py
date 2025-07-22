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
    Creates the 'users' table if it does not already exist.
    Ensures a unique constraint on 'telegram_id'.
    Updated to include new fields: password, age, experience, capital.
    """
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
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
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
    if len(password) < 8:
        logger.warning(f"User {message.from_user.id} entered short password.")
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
        age = int(message.text)
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
    await state.update_data(experience=message.text)
    logger.info(f"User {message.from_user.id} entered experience: {message.text}. Prompting for capital.")
    await message.answer("💰 هل لديك رأس مال صغير لكي تبدأ التجارة الإلكترونية؟ (نعم/لا)")
    await state.set_state(UserData.waiting_capital) # Advance to waiting_capital

@dp.message(UserData.waiting_capital)
async def process_capital(message: types.Message, state: FSMContext):
    """
    Processes user's capital input. Provides payment address and prompts for screenshot.
    """
    await state.update_data(capital=message.text)
    logger.info(f"User {message.from_user.id} entered capital: {message.text}. Prompting for payment screenshot.")

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

@dp.message(F.photo, UserData.waiting_payment) 
async def process_payment(message: types.Message, state: FSMContext):
    """
    Processes the payment screenshot provided by the user.
    Saves or updates user data (Telegram ID, email, password, age, experience, capital, payment image file ID)
    in the database. Clears the FSM state upon completion.
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
                    SET email = $2, password = $3, age = $4, experience = $5, capital = $6, payment_image = $7
                    WHERE telegram_id = $1
                ''', message.from_user.id, data.get('email'), data.get('password'), data.get('age'),
                   data.get('experience'), data.get('capital'), file_id)
                logger.info(f"User {message.from_user.id} updated their full data with screenshot. Telegram File ID: {file_id}")
                await message.answer("✅ تم تحديث بياناتك ودفعك بنجاح. سيتم التحقق يدوياً. شكراً!")
            else:
                await conn.execute('''
                    INSERT INTO users (telegram_id, email, password, age, experience, capital, payment_image)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                ''', message.from_user.id, data.get('email'), data.get('password'), data.get('age'),
                   data.get('experience'), data.get('capital'), file_id)
                logger.info(f"User {message.from_user.id} data saved successfully with screenshot. Telegram File ID: {file_id}")
                await message.answer("✅ تم استلام بياناتك ودفعك بنجاح. سيتم التحقق يدوياً. شكراً!")
    except Exception as e:
        logger.error(f"Error saving/updating data for user {message.from_user.id}: {e}", exc_info=True)
        await message.answer("❌ حدث خطأ أثناء حفظ معلوماتك. الرجاء المحاولة مرة أخرى.")
    finally:
        await state.clear() 

@dp.callback_query(F.data == 'copy_address') 
async def copy_address_callback(callback_query: types.CallbackQuery):
    """
    Handles the callback query when the user clicks 'copy_address' button.
    Sends an alert to the user.
    """
    await callback_query.answer(text="📋 تم نسخ العنوان (انسخه يدوياً)", show_alert=True)
    logger.info(f"User {callback_query.from_user.id} clicked copy address button.")

# --- Generic handlers for unhandled messages ---
# This handler is placed LAST to catch any message not handled by specific filters above.
@dp.message()
async def unhandled_message(message: types.Message):
    """
    Handles any message that does not match specific handlers above.
    Provides a fallback response to the user.
    """
    logger.warning(f"Unhandled message from user {message.from_user.id} ({message.from_user.full_name}): Text='{message.text}' Type='{message.content_type}'")
    
    if message.text and message.text.startswith('/'):
        await message.answer("عذراً، هذا الأمر غير معروف. يرجى البدء باستخدام الأمر /start.")
    elif message.text: # If it's a text message but not a command
        await message.answer("عذراً، لم أفهم طلبك. يرجى البدء باستخدام الأمر /start.")
    else: # For other content types (stickers, voice, etc.) not explicitly handled
        await message.answer("عذراً، لا أستطيع معالجة هذا النوع من الرسائل. يرجى البدء باستخدام الأمر /start.")


# --- Startup and Shutdown Hooks ---

async def on_startup_tasks(dispatcher):
    """
    Tasks to be executed when the bot starts up.
    Initializes database connection pool and creates necessary tables.
    """
    global db_pool
    try:
        db_pool = await create_db_pool()
        await init_db()
        logger.info("Bot is ready and running! Waiting for Telegram updates...")
    except Exception as e:
        logger.critical(f"Failed to start bot due to critical startup tasks (e.g., DB connection): {e}", exc_info=True)
        sys.exit(1) 

async def on_shutdown_tasks(dispatcher):
    """
    Tasks to be executed when the bot is shutting down.
    Closes the database connection pool cleanly.
    """
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed cleanly.")
    logger.info("Bot has been shut down.")

# --- Main function to run the bot ---
async def main():
    """
    The main asynchronous function that registers startup/shutdown hooks
    and starts the bot's polling mechanism.
    """
    dp.startup.register(on_startup_tasks)
    dp.shutdown.register(on_shutdown_tasks)

    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"An unhandled error occurred during bot execution: {e}", exc_info=True)

