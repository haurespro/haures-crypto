import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import asyncpg
import os

# إعدادات البوت
API_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# الاتصال بقاعدة البيانات
async def create_db():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            email TEXT,
            code TEXT,
            payment_proof TEXT
        );
    ''')
    await conn.close()

# الحالة
class Form(StatesGroup):
    email = State()
    code = State()
    payment = State()

# عند البدء
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("✅ مرحب
