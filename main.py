import logging import re from aiogram import Bot, Dispatcher, executor, types from aiogram.contrib.fsm_storage.memory import MemoryStorage from aiogram.dispatcher import FSMContext from aiogram.dispatcher.filters.state import State, StatesGroup from aiogram.dispatcher.filters import Text import psycopg2 import os from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN") DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN) storage = MemoryStorage() dp = Dispatcher(bot, storage=storage)

conn = psycopg2.connect(DATABASE_URL, sslmode='require') cursor = conn.cursor()

cursor.execute(''' CREATE TABLE IF NOT EXISTS users ( id SERIAL PRIMARY KEY, telegram_id BIGINT, email TEXT, secret TEXT, screenshot_file_id TEXT ) ''') conn.commit()

class Form(StatesGroup): email = State() secret = State() age = State() experience = State() capital = State() screenshot = State()

@dp.message_handler(commands='start') async def cmd_start(message: types.Message): user_fullname = message.from_user.full_name welcome_text = ( f"👋 أهلاً {user_fullname} في بوت Haures!")

welcome_text += "\n\n💼 هذا البوت هو أفضل وسيلة للدخول إلى عالم التجارة الإلكترونية بخطوات بسيطة وفعالة!"
welcome_text += "\n✅ سجّل معلوماتك، ادفع عبر USDT، وابدأ رحلتك معنا."
welcome_text += "\n\n🔐 لنبدأ، أرسل لي بريدك الإلكتروني:"

await message.answer(welcome_text)
await Form.email.set()

@dp.message_handler(state=Form.email) async def process_email(message: types.Message, state: FSMContext): if not re.match(r"[^@]+@[^@]+.[^@]+", message.text): await message.answer("❌ بريد إلكتروني غير صالح. حاول مرة أخرى.") return await state.update_data(email=message.text) await Form.next() await message.answer("🔑 أدخل رمزك السري (8 أحرف أو أكثر):")

@dp.message_handler(state=Form.secret) async def process_secret(message: types.Message, state: FSMContext): if len(message.text) < 8: await message.answer("❌ الرمز قصير جدًا. أعد إدخال رمز لا يقل عن 8 أحرف أو أرقام.") return await state.update_data(secret=message.text) await Form.next() await message.answer("🎂 كم عمرك؟")

@dp.message_handler(state=Form.age) async def process_age(message: types.Message, state: FSMContext): try: age = int(message.text) if age < 18: await message.answer("📚 روح تقرا بابا! الخدمة هذه للكبار فقط.") await state.finish() return await Form.next() await message.answer("📊 هل لديك خبرة في التجارة الإلكترونية؟ (نعم / لا)") except ValueError: await message.answer("❌ أدخل رقمًا صحيحًا من فضلك.")

@dp.message_handler(state=Form.experience) async def process_experience(message: types.Message, state: FSMContext): await Form.next() await message.answer("💰 كم هو أقل رأس مال ممكن تبدأ به مشروع؟")

@dp.message_handler(state=Form.capital) async def process_capital(message: types.Message, state: FSMContext): await Form.next() await message.answer( "✅ ممتاز!\n💸 قم الآن بالدفع عبر عنوان USDT (TRC20):\n TLcdVqDCowDiyXKJMDZzVduN1HCS7yZozk\n ثم أرسل لقطة شاشة لإثبات الدفع. 📸", parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().add( types.InlineKeyboardButton("📋 نسخ العنوان", switch_inline_query_current_chat="TLcdVqDCowDiyXKJMDZzVduN1HCS7yZozk") ) )

@dp.message_handler(content_types=types.ContentType.PHOTO, state=Form.screenshot) async def process_screenshot(message: types.Message, state: FSMContext): photo = message.photo[-1] file_id = photo.file_id

user_data = await state.get_data()
telegram_id = message.from_user.id
email = user_data['email']
secret = user_data['secret']

cursor.execute(
    "INSERT INTO users (telegram_id, email, secret, screenshot_file_id) VALUES (%s, %s, %s, %s)",
    (telegram_id, email, secret, file_id)
)
conn.commit()

await message.answer("📥 تم استلام لقطة الشاشة! سيتم التحقق يدويًا من الدفع قريبًا.")
await state.finish()

@dp.message_handler(lambda message: message.text.lower() == 'إلغاء', state='*') async def cancel_handler(message: types.Message, state: FSMContext): await state.finish() await message.answer('❌ تم إلغاء العملية.')

if name == 'main': from aiogram import executor print("✅ البوت قيد التشغيل ...") executor.start_polling(dp, skip_updates=True)

