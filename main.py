import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
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
async def send_welcome(message: Message):
    await message.answer(
        """
🎓 مرحبًا بك في *برنامج Haures التعليمي المجاني*!

🤖 هدفنا هو مساعدتك على دخول عالم التجارة الإلكترونية بطريقة منظمة وسهلة.

📩 سيتم توجيهك خطوة بخطوة:
1. سنطلب بريدك الإلكتروني
2. ثم رمزًا سريًا
3. بعد ذلك، نرسل لك عنوان الدفع
4. وأخيرًا تطلب منا تفعيل اشتراكك بعد إرسال الإثبات

✅ اضغط على "التالي" للانطلاق.
        """,
        parse_mode="Markdown"
    )

async def main():
    print("✅ البوت قيد التشغيل ...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
