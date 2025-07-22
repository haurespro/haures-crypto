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
            min_size=1, # Minimum number of connections in the pool
            max_size=10 # Maximum number of connections in the pool
        )
        logger.info("Database connection pool created successfully.")
        return pool
    except Exception as e:
        logger.critical(f"Failed to create database pool: {e}", exc_info=True)
        raise # Re-raise to ensure startup fails if DB connection cannot be established

async def init_db():
    """
    Creates the 'users' table in the database if it does not already exist.
    Ensures a unique constraint on 'telegram_id'.
    """
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE, -- Ensures each Telegram user ID is unique
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

# Handler for the /start command
# This filter is highly robust, catching any text that starts with '/start'
@dp.message(lambda message: message.text and message.text.startswith('/start')) 
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
    if not message.text: # Basic check for empty message
        await message.answer("❌ يرجى إدخال رمز صالح.")
        return

    await state.update_data(code=message.text)
    logger.info(f"User {message.from_user.id} entered code. Prompting for payment.")

    # Inline keyboard for copying address (aiogram v3.x syntax)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📋 نسخ عنوان الدفع", callback_data="copy_address")
    ]])
    await message.answer(
        "💳 أرسل المبلغ إلى هذا العنوان:\n`TLxUzr...TRC20`", # Consider making this address configurable
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
    file_id = message.photo[-1].file_id # Get the file_id of the largest photo for storage

    try:
        async with db_pool.acquire() as conn:
            # Check if user already exists based on telegram_id to prevent duplicates or update
            existing_user = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1", message.from_user.id
            )
            if existing_user:
                # Update existing user's data
                await conn.execute('''
                    UPDATE users
                    SET email = $2, code = $3, payment_image = $4
                    WHERE telegram_id = $1
                ''', message.from_user.id, data.get('email'), data.get('code'), file_id)
                logger.info(f"User {message.from_user.id} updated their payment details. Telegram File ID: {file_id}")
                await message.answer("✅ تم تحديث بيانات دفعتك. سيتم التحقق يدوياً. شكراً!")
            else:
                # Insert new user data
                await conn.execute('''
                    INSERT INTO users (telegram_id, email, code, payment_image)
                    VALUES ($1, $2, $3, $4)
                ''', message.from_user.id, data.get('email'), data.get('code'), file_id)
                logger.info(f"User {message.from_user.id} data saved successfully. Telegram File ID: {file_id}")
                await message.answer("✅ تم استلام دفعتك. سيتم التحقق يدوياً. شكراً!")
    except Exception as e:
        logger.error(f"Error saving/updating data for user {message.from_user.id}: {e}", exc_info=True)
        await message.answer("❌ حدث خطأ أثناء حفظ معلوماتك. الرجاء المحاولة مرة أخرى.")
    finally:
        await state.clear() # Always clear state after a successful (or failed but final) transaction

# Handler for the inline button callback
@dp.callback_query(F.data == 'copy_address') 
async def copy_address_callback(callback_query: types.CallbackQuery):
    """
    Handles the callback query when the user clicks 'copy_address' button.
    Sends an alert to the user.
    """
    await callback_query.answer(text="📋 تم نسخ العنوان (انسخه يدوياً)", show_alert=True)
    logger.info(f"User {callback_query.from_user.id} clicked copy address button.")

# --- Generic handlers for unhandled messages ---
# This handler should be placed AFTER all specific handlers
# It catches any message that wasn't handled by previous filters.
@dp.message()
async def unhandled_message(message: types.Message):
    """
    Handles any message that does not match specific handlers above.
    Provides a fallback response to the user.
    """
    logger.warning(f"Unhandled message from user {message.from_user.id} ({message.from_user.full_name}): Text='{message.text}' Type='{message.content_type}'")
    # Only reply if it's a text message and not potentially a command that failed to parse
    if message.text and not message.text.startswith('/'): 
        await message.answer("عذراً، لم أفهم طلبك. يرجى البدء باستخدام الأمر /start.")
    elif message.text and message.text.startswith('/'): # If it's a command, but not handled
         await message.answer("عذراً، هذا الأمر غير معروف. يرجى البدء باستخدام الأمر /start.")
    else: # For other content types (stickers, voice, etc.) that are not explicitly handled
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
        # It's crucial to exit the process if essential services like DB cannot start,
        # otherwise the bot will be in a non-functional state.
        sys.exit(1) # Force the process to exit with an error code

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
    # Register startup and shutdown handlers with the Dispatcher
    dp.startup.register(on_startup_tasks)
    dp.shutdown.register(on_shutdown_tasks)

    # Start polling for updates from Telegram.
    # skip_updates=True ensures the bot doesn't process old updates from before it started.
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        # Run the main asynchronous function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"An unhandled error occurred during bot execution: {e}", exc_info=True)

