import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import os

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

class Form(StatesGroup):
    email = State()
    code = State()
    screenshot = State()

@dp.message()
async def start_handler(message: types.Message, state: FSMContext):
    await message.answer("✅ أرسل بريدك الإلكتروني:")
    await state.set_state(Form.email)

@dp.message(Form.email)
async def email_handler(message: types.Message, state: FSMContext):
    await state.update_data(email=message.text)
    await message.answer("🔐 أرسل الرمز السري:")
    await state.set_state(Form.code)

@dp.message(Form.code)
async def code_handler(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    await message.answer("📸 أرسل لقطة الشاشة بعد الدفع:")
    await state.set_state(Form.screenshot)

@dp.message(Form.screenshot)
async def screenshot_handler(message: types.Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        data = await state.get_data()
        await message.answer("✅ تم استلام الدفعة بنجاح!\n📩 سيتم تأكيد حسابك قريبًا.")
        print(f"Email: {data['email']}, Code: {data['code']}, Screenshot: {file_id}")
    else:
        await message.answer("❌ أرسل صورة فقط من فضلك.")
    await state.clear()

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
