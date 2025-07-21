import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
import logging
import os

# إعدادات البوت
TOKEN = os.getenv("BOT_TOKEN") or "ضع_توكن_البوت_هنا"

# إعدادات السجلات
logging.basicConfig(level=logging.INFO)

# إنشاء كائنات البوت والديسباتشر
bot = Bot(token=TOKEN)
dp = Dispatcher()

# الرد على أمر /start
@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    welcome_text = (
        "🎓 *مرحبًا بك في برنامج Haures التعليمي المجاني!*\n\n"
        "🤖 هدفنا هو مساعدتك على دخول عالم التجارة الإلكترونية بطريقة منظمة وسهلة.\n\n"
        "📩 سيتم توجيهك خطوة بخطوة:\n"
        "1. سنطلب بريدك الإلكتروني\n"
        "2. ثم رمزًا سريًا\n"
        "3. بعد ذلك، نرسل لك عنوان الدفع\n"
        "4. وأخيرًا تطلب منا تفعيل اشتراكك بعد إرسال الإثبات\n\n"
        "✅ اضغط على \"التالي\" للانطلاق."
    )
    await message.answer(welcome_text, parse_mode="Markdown")

async def main():
    print("✅ البوت قيد التشغيل ...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
