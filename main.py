from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
import psycopg2
import logging

# إعدادات تسجيل الدخول
logging.basicConfig(level=logging.INFO)

# تعريف التوكن الخاص بالبوت
API_TOKEN = "TU_BOT_TOKEN"

# إعداد البوت والمخزن المؤقت
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# إعداد الاتصال بقاعدة البيانات
conn = psycopg2.connect(
    dbname="DB_NAME",
    user="DB_USER",
    password="DB_PASS",
    host="DB_HOST",
    port="5432"
)
cursor = conn.cursor()

# تعريف الحالات
class Form(StatesGroup):
    email = State()
    code = State()
    payment = State()

# بدء البوت
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await Form.email.set()
    await message.answer("👋 مرحبا بك! من فضلك أرسل بريدك الإلكتروني:")

@dp.message_handler(state=Form.email)
async def process_email(message: types.Message, state: FSMContext):
    await state.update_data(email=message.text)
    await Form.next()
    await message.answer("✅ تم استلام البريد. الآن أرسل الرمز السري (8 أحرف على الأقل):")

@dp.message_handler(state=Form.code)
async def process_code(message: types.Message, state: FSMContext):
    if len(message.text) < 8:
        await message.answer("❌ الرمز السري يجب أن يكون 8 أحرف أو أكثر.")
        return
    await state.update_data(code=message.text)
    await Form.next()
    await message.answer("💸 أرسل الآن لقطة شاشة بعد الدفع.")

@dp.message_handler(content_types=['photo'], state=Form.payment)
async def process_payment(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    user_data = await state.get_data()

    cursor.execute(
        "INSERT INTO users (email, code, file_id) VALUES (%s, %s, %s)",
        (user_data['email'], user_data['code'], file_id)
    )
    conn.commit()

    await message.answer("✅ تم استلام إثبات الدفع. سيتم مراجعته قريبًا.")
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
