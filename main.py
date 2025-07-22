import logging
import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncpg

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment Variables (fetched from Render settings)
API_TOKEN = os.getenv("BOT_TOKEN")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

# Ensure API_TOKEN is set
if not API_TOKEN:
    logger.error("BOT_TOKEN environment variable is not set. Please set it in Render.")
    # Exiting the program is crucial if the bot cannot authenticate
    exit("BOT_TOKEN is missing. Exiting.")

# Bot and Dispatcher setup
bot = Bot(token=API_TOKEN)
# Dispatcher is initialized without 'bot' directly in aiogram v3.x
dp = Dispatcher(storage=MemoryStorage()) 

# Database connection pool
db_pool = None

async def create_db_pool():
    """Initializes the database connection pool."""
    if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_HOST]):
        logger.error("One or more database environment variables are not set! Please check Render settings.")
        raise ValueError("Missing database environment variables.")
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
        logger.critical(f"Failed to create database pool: {e}")
        raise # Re-raise the exception to stop the application if DB fails

async def init_db():
    """Creates the 'users' table if it does not exist."""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE, -- Added UNIQUE constraint for telegram_id
                email TEXT,
                code TEXT,
                payment_image TEXT
            );
        ''')
    logger.info("Database table 'users' checked/created successfully.")

# FSM States
class UserData(StatesGroup):
    """States for user data collection."""
    waiting_email = State()
    waiting_code = State()
    waiting_payment = State()

# --- Handlers ---

@dp.message(F.command("start")) # Updated: Use F.command for filtering commands
async def send_welcome(message: types.Message, state: FSMContext):
    """Handles the /start command and initiates the email collection."""
    logger.info(f"User {message.from_user.id} started the bot.")
    await message.answer("👋 مرحباً بك!\nأدخل بريدك الإلكتروني:")
    await state.set_state(UserData.waiting_email)

@dp.message(UserData.waiting_email)
async def process_email(message: types.Message, state: FSMContext):
    """Processes the user's email."""
    # Basic email validation
    if "@" not in message.text or "." not in message.text:
        await message.answer("❌ يرجى إدخال بريد إلكتروني صالح.")
        return

    await state.update_data(email=message.text)
    logger.info(f"User {message.from_user.id} entered email: {message.text}")
    await message.answer("✅ أدخل الرمز السري:")
    await state.set_state(UserData.waiting_code)

@dp.message(UserData.waiting_code)
async def process_code(message: types.Message, state: FSMContext):
    """Processes the user's secret code."""
    await state.update_data(code=message.text)
    logger.info(f"User {message.from_user.id} entered code.")

    # Inline keyboard setup for aiogram v3.x
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

@dp.message(F.photo, UserData.waiting_payment) # Use F.photo for photo content type filtering
async def process_payment(message: types.Message, state: FSMContext):
    """Processes the payment screenshot and saves user data."""
    data = await state.get_data()
    file_id = message.photo[-1].file_id # Get the file_id of the largest photo

    try:
        async with db_pool.acquire() as conn:
            # Check if user already exists based on telegram_id
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
                logger.info(f"User {message.from_user.id} updated their payment details.")
                await message.answer("✅ تم تحديث بيانات دفعتك. سيتم التحقق يدوياً. شكراً!")
            else:
                # Insert new user data
                await conn.execute('''
                    INSERT INTO users (telegram_id, email, code, payment_image)
                    VALUES ($1, $2, $3, $4)
                ''', message.from_user.id, data.get('email'), data.get('code'), file_id)
                logger.info(f"User {message.from_user.id} data saved successfully.")
                await message.answer("✅ تم استلام دفعتك. سيتم التحقق يدوياً. شكراً!")
    except Exception as e:
        logger.error(f"Error inserting/updating data for user {message.from_user.id}: {e}", exc_info=True)
        await message.answer("❌ حدث خطأ أثناء حفظ معلوماتك. الرجاء المحاولة مرة أخرى.")
    finally:
        await state.clear() # Clear state after processing

@dp.callback_query(F.data == 'copy_address') # Use F.data for callback data filtering
async def copy_address_callback(callback_query: types.CallbackQuery):
    """Handles the callback for copying the payment address."""
    # Use callback_query.answer for inline keyboard callbacks in aiogram v3.x
    await callback_query.answer(text="📋 تم نسخ العنوان (انسخه يدوياً)", show_alert=True)
    logger.info(f"User {callback_query.from_user.id} clicked copy address.")

# --- Startup and Shutdown Hooks ---

async def on_startup_tasks(dispatcher):
    """Tasks to run on bot startup."""
    global db_pool
    try:
        db_pool = await create_db_pool()
        await init_db()
        logger.info("Bot is ready and running!")
    except Exception as e:
        logger.critical(f"Failed to start bot due to startup tasks: {e}", exc_info=True)
        # It's critical to exit if essential services like DB cannot start
        # Consider re-raising or sys.exit() if running as a service
        await dispatcher.bot.send_message(
            chat_id=os.getenv("ADMIN_CHAT_ID"), # Optional: send error to admin if you set ADMIN_CHAT_ID
            text=f"🔴 Bot startup failed: {e}"
        )
        # sys.exit(1) # Uncomment if you want the process to exit immediately on startup failure

async def on_shutdown_tasks(dispatcher):
    """Tasks to run on bot shutdown."""
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed.")
    logger.info("Bot has been shut down.")

# Main function to run the bot
async def main():
    """Main function to start the bot."""
    # Register startup and shutdown handlers
    dp.startup.register(on_startup_tasks)
    dp.shutdown.register(on_shutdown_tasks)

    # Start polling, passing the bot instance to it
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        # Run the asynchronous main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"An unhandled error occurred during bot execution: {e}", exc_info=True)
        
