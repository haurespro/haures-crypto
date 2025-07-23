from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
import psycopg2
import logging
import os # لإدارة متغيرات البيئة

# إعدادات تسجيل الدخول
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# تعريف التوكن الخاص بالبوت
# يُفضل استخدام متغيرات البيئة للتوكن والمعلومات الحساسة
# API_TOKEN = os.getenv("BOT_TOKEN", "ضع_توكن_البوت_هنا_في_حالة_عدم_وجوده_كمتغير_بيئة")
API_TOKEN = "TU_BOT_TOKEN" # لا تنسى تغيير هذا بجدول التوكن الخاص بك

# إعداد البوت والمخزن المؤقت
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# إعداد الاتصال بقاعدة البيانات
# يُفضل استخدام متغيرات البيئة لمعلومات قاعدة البيانات
DB_NAME = os.getenv("DB_NAME", "DB_NAME") # استبدل 'DB_NAME' باسم قاعدة بياناتك
DB_USER = os.getenv("DB_USER", "DB_USER") # استبدل 'DB_USER' باسم المستخدم
DB_PASS = os.getenv("DB_PASS", "DB_PASS") # استبدل 'DB_PASS' بكلمة المرور
DB_HOST = os.getenv("DB_HOST", "DB_HOST") # استبدل 'DB_HOST' بالمضيف
DB_PORT = os.getenv("DB_PORT", "5432") # استبدل '5432' بالمنفذ إذا كان مختلفًا

conn = None # تهيئة المتغير خارج try بلوك
cursor = None # تهيئة المتغير خارج try بلوك

try:
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()
    logger.info("تم الاتصال بقاعدة البيانات بنجاح.")

    # تأكد من وجود الجدول 'users' (اختياري، يمكنك القيام بذلك يدويًا أو عبر Migration)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            code VARCHAR(255) NOT NULL,
            file_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    logger.info("تم التحقق من جدول المستخدمين (users) أو إنشاؤه.")

except Exception as e:
    logger.error(f"فشل الاتصال بقاعدة البيانات: {e}")
    # يمكنك هنا اتخاذ إجراءات أخرى، مثل إيقاف البوت
    # exit(1) # لإيقاف التطبيق إذا فشل الاتصال بقاعدة البيانات

# تعريف الحالات
class Form(StatesGroup):
    email = State()
    code = State()
    payment = State()

# بدء البوت
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    # التأكد من أن قاعدة البيانات متصلة قبل البدء
    if conn is None or conn.closed:
        logger.error("البوت حاول البدء ولكن الاتصال بقاعدة البيانات غير موجود أو مغلق.")
        await message.answer("عذراً، هناك مشكلة فنية حالياً. يرجى المحاولة لاحقاً.")
        return

    await Form.email.set()
    await message.answer("👋 مرحبا بك! من فضلك أرسل بريدك الإلكتروني:")

@dp.message_handler(state=Form.email)
async def process_email(message: types.Message, state: FSMContext):
    user_email = message.text.strip() # إزالة المسافات البيضاء الزائدة

    # يمكنك إضافة تحقق بسيط لنمط البريد الإلكتروني هنا إذا أردت
    if "@" not in user_email or "." not in user_email:
        await message.answer("❌ يبدو أن هذا ليس بريداً إلكترونياً صالحاً. يرجى إدخال بريد إلكتروني صحيح:")
        return

    await state.update_data(email=user_email)
    await Form.next()
    await message.answer("✅ تم استلام البريد. الآن أرسل الرمز السري (8 أحرف أو أكثر):")

@dp.message_handler(state=Form.code)
async def process_code(message: types.Message, state: FSMContext):
    user_code = message.text.strip()
    if len(user_code) < 8:
        await message.answer("❌ الرمز السري يجب أن يكون 8 أحرف أو أكثر. من فضلك أدخل رمزاً سرياً أطول:")
        return
    await state.update_data(code=user_code)
    await Form.next()
    await message.answer("💸 يرجى إرسال لقطة شاشة بعد الدفع الآن. تأكد من أنها صورة واضحة:")

@dp.message_handler(content_types=['photo'], state=Form.payment)
async def process_payment(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    user_data = await state.get_data()

    try:
        cursor.execute(
            "INSERT INTO users (email, code, file_id) VALUES (%s, %s, %s)",
            (user_data['email'], user_data['code'], file_id)
        )
        conn.commit()
        logger.info(f"تم حفظ بيانات المستخدم: {user_data['email']}")
        await message.answer("✅ تم استلام إثبات الدفع بنجاح! سيتم مراجعته في أقرب وقت.")
        await state.finish()
    except psycopg2.errors.UniqueViolation:
        conn.rollback() # التراجع عن المعاملة في حالة وجود خطأ
        logger.warning(f"محاولة تسجيل بريد إلكتروني موجود مسبقاً: {user_data['email']}")
        await message.answer("⚠️ البريد الإلكتروني هذا مسجل لدينا بالفعل. يرجى استخدام بريد إلكتروني آخر أو التواصل مع الدعم.")
        await state.finish() # إنهاء الحالة للسماح للمستخدم بالبدء من جديد
    except Exception as e:
        conn.rollback() # التراجع عن المعاملة في حالة وجود خطأ
        logger.error(f"خطأ أثناء حفظ البيانات في قاعدة البيانات: {e}", exc_info=True)
        await message.answer("❌ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى لاحقًا أو التواصل مع الدعم.")
        await state.finish() # إنهاء الحالة لتجنب التعليق

@dp.message_handler(state=Form.payment)
async def process_payment_invalid(message: types.Message, state: FSMContext):
    # هذا المعالج سيتلقى أي رسالة ليست صورة في حالة Form.payment
    await message.answer("❌ من فضلك أرسل لقطة شاشة (صورة) فقط لإثبات الدفع. لا ترسل نصًا.")

# إغلاق الاتصال بقاعدة البيانات عند إيقاف البوت
async def on_shutdown(dispatcher: Dispatcher):
    if cursor:
        cursor.close()
        logger.info("تم إغلاق مؤشر قاعدة البيانات.")
    if conn:
        conn.close()
        logger.info("تم إغلاق الاتصال بقاعدة البيانات.")

if __name__ == '__main__':
    # تأكد من أن الاتصال بقاعدة البيانات قد تم بنجاح قبل بدء البوت
    if conn:
        executor.start_polling(dp, skip_updates=True, on_shutdown=on_shutdown)
    else:
        logger.critical("فشل بدء البوت بسبب عدم وجود اتصال بقاعدة البيانات.")


