import logging
import os
import asyncio # إضافة مكتبة asyncio
from aiogram import Bot, Dispatcher, types, F # إضافة F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
# تم إزالة: from aiogram.utils import executor
from aiogram.fsm.storage.memory import MemoryStorage # تغيير المسار لتخزين FSM
from aiogram.fsm.context import FSMContext # تغيير المسار لـ FSMContext
from aiogram.fsm.state import State, StatesGroup # تغيير المسار لـ State, StatesGroup
import asyncpg

# إعداد التسجيل (Logging)
logging.basicConfig(level=logging.INFO)

# متغيرات البيئة (سيتم جلبها من إعدادات Render)
API_TOKEN = os.getenv("BOT_TOKEN")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

# إعداد البوت والديسباتشر
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage()) # تحديد التخزين هنا

# تهيئة تجمع الاتصال بقاعدة البيانات
db_pool = None

async def create_db_pool():
    # التحقق من أن جميع متغيرات قاعدة البيانات موجودة
    if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_HOST]):
        logging.error("Database environment variables are not fully set! Please check Render settings.")
        raise ValueError("Missing database environment variables.")
    return await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST
    )

# إنشاء الجدول إذا لم يكن موجوداً
async def init_db():
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT,
                email TEXT,
                code TEXT,
                payment_image TEXT
            );
        ''')
    logging.info("Database table 'users' checked/created successfully.")


# FSM - تعريف الحالات (States)
class UserData(StatesGroup):
    waiting_email = State()
    waiting_code = State()
    waiting_payment = State()

# بداية المحادثة
@dp.message(commands=['start']) # تغيير: استخدام @dp.message بدلاً من @dp.message_handler
async def send_welcome(message: types.Message, state: FSMContext): # إضافة state
    await message.answer("👋 مرحباً بك!\nأدخل بريدك الإلكتروني:")
    await state.set_state(UserData.waiting_email) # تغيير: استخدام set_state


# معالجة البريد الإلكتروني
@dp.message(UserData.waiting_email) # تغيير: استخدام @dp.message
async def process_email(message: types.Message, state: FSMContext):
    await state.update_data(email=message.text)
    await message.answer("✅ أدخل الرمز السري:")
    await state.set_state(UserData.waiting_code) # تغيير: استخدام set_state

# معالجة الرمز السري
@dp.message(UserData.waiting_code) # تغيير: استخدام @dp.message
async def process_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[ # تغيير: طريقة إنشاء InlineKeyboardMarkup
        InlineKeyboardButton(text="📋 نسخ عنوان الدفع", callback_data="copy")
    ]])
    await message.answer("💳 أرسل المبلغ إلى هذا العنوان:\n`TLxUzr...TRC20`", parse_mode="Markdown", reply_markup=keyboard)
    await message.answer("📷 أرسل لقطة الشاشة كدليل على الدفع:")
    await state.set_state(UserData.waiting_payment) # تغيير: استخدام set_state

# معالجة لقطة الشاشة (إثبات الدفع)
@dp.message(F.photo, UserData.waiting_payment) # تغيير: استخدام @dp.message و F.photo
async def process_payment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.photo[-1].file_id

    try:
        async with db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO users (telegram_id, email, code, payment_image)
                VALUES ($1, $2, $3, $4)
            ''', message.from_user.id, data['email'], data['code'], file_id)
        await message.answer("✅ تم استلام الدفعة. سيتم التحقق يدوياً. شكراً!")
    except Exception as e:
        logging.error(f"Error inserting data into DB: {e}")
        await message.answer("❌ حدث خطأ أثناء حفظ معلوماتك. الرجاء المحاولة مرة أخرى.")
    finally:
        await state.clear() # تغيير: استخدام state.clear() بدلاً من state.finish()

# معالجة زر النسخ (للإظهار فقط، لا ينسخ فعلياً)
@dp.callback_query(F.data == 'copy') # تغيير: استخدام @dp.callback_query و F.data
async def copy_address(callback_query: types.CallbackQuery):
    await callback_query.answer(text="📋 تم نسخ العنوان (انسخه يدوياً)") # تغيير: استخدام callback_query.answer

# دالة التشغيل عند بدء البوت (on_startup)
async def on_startup(dispatcher):
    global db_pool
    db_pool = await create_db_pool()
    await init_db()
    logging.info("✅ البوت جاهز للعمل...")

# تشغيل البوت باستخدام Polling
async def main():
    await on_startup(dp) # استدعاء دالة on_startup يدوياً
    await dp.start_polling(bot, skip_updates=True) # طريقة التشغيل الجديدة في aiogram v3.x

if __name__ == '__main__':
    asyncio.run(main()) # تشغيل دالة main غير المتزامنة
