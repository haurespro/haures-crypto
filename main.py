import os
import logging
import psycopg2
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.executor import start_webhook, start_polling # سنستخدم start_webhook

# --- إعدادات التسجيل ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- تعريف متغيرات البيئة (مهم جداً لـ Render) ---
# يجب عليك إضافة هذه المتغيرات في إعدادات Render كـ Environment Variables
API_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL") # هذا أفضل لـ Render للاتصال بـ PostgreSQL

# --- إعدادات Webhook (خاصة بـ Render) ---
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") # URL لخدمة الويب الخاصة بك على Render (مثال: https://your-bot-name.onrender.com)
WEBHOOK_PATH = f"/webhook/{API_TOKEN}" # مسار الـ Webhook
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# --- إعداد البوت والمخزن المؤقت ---
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- إعداد الاتصال بقاعدة البيانات ---
conn = None
cursor = None

async def setup_db():
    global conn, cursor
    try:
        # Render يستخدم DATABASE_URL لـ PostgreSQL
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        logger.info("تم الاتصال بقاعدة البيانات بنجاح.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS program_sales (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                secret_code VARCHAR(255) NOT NULL,
                payment_screenshot_file_id TEXT NOT NULL,
                submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        logger.info("تم التحقق من جدول مبيعات البرنامج (program_sales) أو إنشاؤه.")
        return True
    except Exception as e:
        logger.critical(f"فشل الاتصال بقاعدة البيانات أو إعداد الجدول: {e}", exc_info=True)
        return False

# --- تعريف الحالات (Forms) ---
class ProgramPurchase(StatesGroup):
    email = State()
    secret_code = State()
    payment_proof = State()

# --- معالجات الأوامر والرسائل ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    logger.info(f"Received /start command from user: {message.from_user.id}")
    if conn is None or conn.closed:
        logger.error("البوت حاول البدء ولكن الاتصال بقاعدة البيانات غير موجود أو مغلق.")
        await message.answer("عذراً، هناك مشكلة فنية حالياً. يرجى المحاولة لاحقاً.")
        return

    await ProgramPurchase.email.set()
    await message.answer(
       """👋 مرحباً بك! هل أنت مستعد لتعلم أسرار التجارة الإلكترونية؟
"""
       """للبدء، يرجى إرسال بريدك الإلكتروني للحصول على تفاصيل البرنامج:"""
    )

@dp.message_handler(state=ProgramPurchase.email)
async def process_email(message: types.Message, state: FSMContext):
    user_email = message.text.strip()
    if "@" not in user_email or "." not in user_email or len(user_email) < 5:
        await message.answer("❌ هذا ليس بريداً إلكترونياً صالحاً. يرجى إدخال بريد إلكتروني صحيح:")
        return

    await state.update_data(email=user_email)
    await ProgramPurchase.next()
    await message.answer(
        """✅ تم استلام بريدك الإلكتروني بنجاح! سيتم إرسال بعض التفاصيل إليك قريباً.
"""
        """الآن، من فضلك أرسل الرمز السري الخاص بالبرنامج (8 أحرف أو أكثر):"""
    )

@dp.message_handler(state=ProgramPurchase.secret_code)
async def process_secret_code(message: types.Message, state: FSMContext):
    code_text = message.text.strip()
    if len(code_text) < 8:
        await message.answer("❌ الرمز السري يجب أن يكون 8 أحرف أو أكثر. يرجى إدخال رمز سري أطول:")
        return

    await state.update_data(secret_code=code_text)
    await ProgramPurchase.next()
    await message.answer(
    """💸 ممتاز! الرمز السري صحيح.
لإتمام عملية الشراء وتلقي البرنامج، يرجى إرسال لقطة شاشة (صورة) تثبت إتمام عملية الدفع.
تأكد أن الصورة واضحة وتظهر تفاصيل الدفع."""
)@dp.message_handler(content_types=types.ContentTypes.PHOTO, state=ProgramPurchase.payment_proof)
async def process_payment_proof(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id # الحصول على أكبر نسخة من الصورة
    user_data = await state.get_data()

    try:
        cursor.execute(
            "INSERT INTO program_sales (email, secret_code, payment_screenshot_file_id) VALUES (%s, %s, %s)",
            (user_data['email'], user_data['secret_code'], file_id)
        )
        conn.commit()
        logger.info(f"تم حفظ بيانات بيع البرنامج للمستخدم: {user_data['email']}")
        await message.answer(
    """🎉 رائع! تم استلام إثبات الدفع بنجاح.
فريقنا سيقوم بمراجعة الدفع في أقرب وقت ممكن. بعد التأكيد، ستتلقى البرنامج عبر البريد الإلكتروني الذي قدمته.
شكراً لك لانضمامك إلى برنامج تعلم التجارة الإلكترونية!"""
)
        await state.finish()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        logger.warning(f"محاولة تسجيل بريد إلكتروني موجود مسبقاً في مبيعات البرنامج: {user_data['email']}")
        await message.answer(
            "⚠️ عذراً، يبدو أن هذا البريد الإلكتروني مسجل لدينا بالفعل ضمن طلب شراء سابق."
            " إذا كنت تواجه مشكلة، يرجى التواصل مع الدعم."
        )
        await state.finish()
    except Exception as e:
        conn.rollback()
        logger.error(f"خطأ أثناء حفظ بيانات مبيعات البرنامج في قاعدة البيانات: {e}", exc_info=True)
        await message.answer(
            "❌ حدث خطأ غير متوقع أثناء معالجة طلبك. يرجى المحاولة مرة أخرى لاحقًا أو التواصل مع الدعم."
        )
        await state.finish()

@dp.message_handler(state=ProgramPurchase.payment_proof)
async def process_payment_proof_invalid(message: types.Message, state: FSMContext):
    # يتعامل مع الرسائل التي ليست صوراً في هذه الحالة
    await message.answer("❌ من فضلك أرسل لقطة شاشة (صورة) فقط لإثبات الدفع. لا ترسل نصًا أو أنواع ملفات أخرى.")

# --- دوال بدء وإيقاف الـ Webhook ---

async def on_startup(dp):
    logger.info("Bot is starting up...")
    db_ready = await setup_db()
    if not db_ready:
        logger.critical("فشل إعداد قاعدة البيانات. البوت لن يعمل بشكل صحيح.")
        # يمكنك اختيار إيقاف البوت هنا إذا كان اتصال قاعدة البيانات حاسمًا
        # exit(1)

    # ضبط الـ webhook لـ Telegram API
    webhook_set = await bot.set_webhook(WEBHOOK_URL)
    if webhook_set:
        logger.info(f"Webhook set to: {WEBHOOK_URL}")
    else:
        logger.error("فشل في ضبط الـ Webhook. تحقق من URL البوت وتوكن البوت.")

async def on_shutdown(dp):
    logger.info("Bot is shutting down...")
    # حذف الـ webhook عند إيقاف البوت
    await bot.delete_webhook()
    logger.info("Webhook deleted.")
    if cursor:
        cursor.close()
        logger.info("تم إغلاق مؤشر قاعدة البيانات.")
    if conn:
        conn.close()
        logger.info("تم إغلاق الاتصال بقاعدة البيانات.")

# --- تشغيل البوت ---
if __name__ == '__main__':
    # تأكد أن جميع متغيرات البيئة الأساسية موجودة
    if not API_TOKEN or not DATABASE_URL or not WEBHOOK_HOST:
        logger.critical("متغيرات البيئة BOT_TOKEN, DATABASE_URL, WEBHOOK_HOST غير معرفة. البوت لا يمكن أن يبدأ.")
        exit(1) # إيقاف البوت إذا كانت المتغيرات الأساسية مفقودة

    # ابدأ تشغيل البوت كـ Webhook
    # Render سيستخدم المنفذ الذي يوفره متغير البيئة PORT
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True, # لا تفوت التحديثات القديمة أثناء بدء التشغيل
        host='0.0.0.0', # عنوان الاستماع
        port=int(os.getenv("PORT", 8080)) # المنفذ الذي يوفره Render
    )

