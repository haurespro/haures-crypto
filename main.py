from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InputFile
import asyncio
import logging

API_TOKEN = 'ضع_توكن_البوت_هنا'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply(
        "🎓 مرحبًا بك في *برنامج Haures التعليمي المجاني*\n\n"
        "✅ يرجى قراءة الشروط التالية قبل المتابعة:\n"
        "1. احترام شروط الاستخدام.\n"
        "2. عدم مشاركة الرمز السري مع أي شخص.\n\n"
        "📧 من فضلك أرسل بريدك الإلكتروني:"
    )

# هنا تواصل بإضافة الهاندلر الخاص بالإيميل، الرمز السري، إثبات الدفع، الخ...

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
