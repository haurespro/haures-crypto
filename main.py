import logging
from aiogram import Bot, Dispatcher, executor, types
import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
TRC20_ADDRESS = os.getenv("TRC20_ADDRESS")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# تخزين بيانات المستخدمين مؤقتاً (مثال)
user_data = {}

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer("🎓 مرحبًا بك في *برنامج Haures التعليمي المجاني*\n\n"
                         "✅ للمشاركة، يجب الموافقة على الشروط.\n\n"
                         "أرسل بريدك الإلكتروني للمتابعة.", parse_mode="Markdown")
    user_data[message.from_user.id] = {}

@dp.message_handler(lambda message: "@" in message.text and "." in message.text)
async def process_email(message: types.Message):
    user_data[message.from_user.id]["email"] = message.text
    await message.answer("✅ تم تسجيل بريدك الإلكتروني.\n\nالآن، أرسل الرمز السري الخاص بك.")

@dp.message_handler(lambda message: message.from_user.id in user_data and "email" in user_data[message.from_user.id] and "secret" not in user_data[message.from_user.id])
async def process_secret_code(message: types.Message):
    user_data[message.from_user.id]["secret"] = message.text
    await message.answer(f"📨 استخدم عنوان الدفع التالي (USDT - TRC20):\n`{TRC20_ADDRESS}`\n\n📸 من فضلك، بعد الدفع، أرسل لقطة شاشة كإثبات.", parse_mode="Markdown")

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_screenshot(message: types.Message):
    file_id = message.photo[-1].file_id
    user_data[message.from_user.id]["screenshot_file_id"] = file_id
    await message.answer("✅ تم استلام إثبات الدفع. سيتم التحقق يدويًا قريبًا.\n\nشكرًا لمشاركتك!")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
