import re
import time
import telebot
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== التوكن والإعدادات =====
TOKEN = "7671449403:AAFgbTGaoxMRi5RNTJ0EoMukNNnLK9kjdUc"
bot = telebot.TeleBot(TOKEN)

# ===== معرفات المطورين =====
ADMIN_IDS = [7498653159, 98764321]

# ===== روابط القنوات =====
CHANNEL_TELEGRAM = "https://t.me/ElJokerTechX"
CHANNEL_WHATSAPP = "https://whatsapp.com/channel/0029Vb6mJg61SWsuotwwDR0R"

# ===== كاش الاشتراك =====
subscribed_users = set()        # المستخدمين المكتملين
subscription_steps = {}         # {user_id: 'telegram' or 'whatsapp' or 'completed'}

# ===== إعدادات البحث =====
BASE_URL = "https://than.nezakr.net/?system=s1&t=glos&k={}"
CACHE_DURATION = 3600
cache = {}
users_set = set()
total_requests = 0
start_time = datetime.now()

# ===== دوال الحالة =====
def is_subscribed(user_id):
    return user_id in subscribed_users

def get_sub_step(user_id):
    return subscription_steps.get(user_id, None)

def set_sub_step(user_id, step):
    subscription_steps[user_id] = step

def mark_subscribed(user_id):
    subscribed_users.add(user_id)
    if user_id in subscription_steps:
        del subscription_steps[user_id]

# ===== دالة عرض التسلسل =====
def show_subscription_sequence(message):
    user_id = message.from_user.id
    step = get_sub_step(user_id)

    if step is None:
        # الخطوة 1: تليجرام
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📢 اشترك في تليجرام", url=CHANNEL_TELEGRAM),
            InlineKeyboardButton("✅ تم الاشتراك في تليجرام", callback_data="sub_telegram")
        )
        bot.reply_to(
            message,
            "🔒 **الخطوة 1 من 2:**\n\n"
            "• اضغط على زر **اشترك في تليجرام** واشترك في القناة.\n"
            "• ثم اضغط على **تم الاشتراك في تليجرام** للمتابعة.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        set_sub_step(user_id, 'telegram')
        return False

    elif step == 'telegram':
        # الخطوة 2: واتساب
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("💬 اشترك في واتساب", url=CHANNEL_WHATSAPP),
            InlineKeyboardButton("✅ تم الاشتراك في واتساب", callback_data="sub_whatsapp")
        )
        bot.reply_to(
            message,
            "🔒 **الخطوة 2 من 2:**\n\n"
            "• اضغط على زر **اشترك في واتساب** واشترك في القناة.\n"
            "• ثم اضغط على **تم الاشتراك في واتساب** لتفعيل البوت.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        set_sub_step(user_id, 'whatsapp')
        return False

    elif step == 'whatsapp':
        # الخطوة النهائية: تفعيل
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 تفعيل البوت الآن", callback_data="activate_bot"))
        bot.reply_to(
            message,
            "✅ **تهانينا!**\n\n"
            "لقد أكملت جميع خطوات الاشتراك.\n"
            "اضغط على **تفعيل البوت الآن** لبدء الاستخدام.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        # نضع الحالة إلى 'ready' لمعرفة أنه في الخطوة الأخيرة
        set_sub_step(user_id, 'ready')
        return False

    elif step == 'ready':
        # إذا كان في حالة ready ولكن لم يضغط على التفعيل بعد، نعيد عرض زر التفعيل
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 تفعيل البوت الآن", callback_data="activate_bot"))
        bot.reply_to(
            message,
            "✅ اضغط على **تفعيل البوت الآن** لبدء الاستخدام.",
            reply_markup=markup
        )
        return False

    # إذا كان مشتركاً بالفعل، نعود True
    return True

# ===== دالة ensure_subscription المحسنة =====
def ensure_subscription(message):
    user_id = message.from_user.id
    if is_subscribed(user_id):
        return True

    # نمرر الرسالة لعرض التسلسل
    return show_subscription_sequence(message)

# ===== دوال جلب البيانات (بدون تغيير) =====
def get_student_data(seat: str, retries=3):
    url = BASE_URL.format(seat)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "ar-EG,ar;q=0.9",
    }

    resp = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                break
        except Exception as e:
            if attempt == retries:
                return None, f"❌ فشل الاتصال بعد {retries} محاولات: {e}"
            time.sleep(1)
    else:
        return None, f"❌ الموقع لم يستجب بعد {retries} محاولات (HTTP {resp.status_code})"

    soup = BeautifulSoup(resp.text, "html.parser")
    body_text = soup.get_text()

    name = "غير معروف"
    title = soup.find("title")
    if title:
        m = re.search(r"نتيجة الطالب (.*?) في", title.text)
        if m:
            name = m.group(1).strip()

    def extract(label):
        pattern = re.compile(rf"{label}\s*([^\n\d]+?)(?:\d|\n|$)")
        match = pattern.search(body_text)
        return match.group(1).strip() if match else "غير محدد"

    section = extract("الشعبة")
    edu_type = extract("نوع التعليم")
    raw_grade = extract("التقدير")

    subjects = {}
    total_earned = 0.0
    total_max = 0.0

    subject_rows = soup.select('div.nzk-subject-row')
    if subject_rows:
        for row in subject_rows:
            name_elem = row.select_one('.nzk-subject-name')
            if not name_elem:
                continue
            subj = name_elem.get_text(strip=True)
            score_elem = row.select_one('.nzk-subject-score')
            if not score_elem:
                continue
            score_text = score_elem.get_text(strip=True)
            match = re.search(r'(\d+\.?\d*)\s*\/\s*(\d+\.?\d*)', score_text)
            if match:
                earned = float(match.group(1))
                max_score = float(match.group(2))
                if max_score > 0:
                    subj = re.sub(r'[0-9]', '', subj).strip()
                    if subj and subj not in ["المادة", "الدرجة", "التقدير", "المستوى", "المجموع"]:
                        percent = (earned / max_score) * 100
                        subjects[subj] = {"earned": earned, "max": max_score, "percent": round(percent, 2)}
                        total_earned += earned
                        total_max += max_score

    if not subjects:
        tables = soup.find_all("table")
        grade_table = None
        for table in tables:
            if "المادة" in table.get_text() and ("الدرجة" in table.get_text() or "المجموع" in table.get_text()):
                grade_table = table
                break

        if grade_table:
            rows = grade_table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    subj = cols[0].get_text(strip=True)
                    score_text = cols[1].get_text(strip=True)
                    if "/" in score_text:
                        parts = score_text.split("/")
                        try:
                            earned = float(parts[0].strip())
                            max_score = float(parts[1].strip())
                        except ValueError:
                            continue
                        if max_score > 0:
                            subj = re.sub(r"[0-9]", "", subj).strip()
                            if subj and subj not in ["المادة", "الدرجة", "التقدير", "المستوى", "المجموع"]:
                                percent = (earned / max_score) * 100
                                subjects[subj] = {"earned": earned, "max": max_score, "percent": round(percent, 2)}
                                total_earned += earned
                                total_max += max_score

    if not subjects:
        lines = body_text.split("\n")
        for line in lines:
            line = line.strip()
            match = re.match(r"^([\u0600-\u06FF\s]{2,}?)\s*(\d+\.?\d*)\s*\/\s*(\d+\.?\d*)", line)
            if match:
                subj = match.group(1).strip()
                earned = float(match.group(2))
                max_score = float(match.group(3))
                if subj and subj not in ["المادة", "الدرجة", "التقدير", "المستوى", "الصف", "الفصل", "المجموع"] and max_score > 0:
                    subj = re.sub(r"[0-9]", "", subj).strip()
                    if subj:
                        percent = (earned / max_score) * 100
                        subjects[subj] = {"earned": earned, "max": max_score, "percent": round(percent, 2)}
                        total_earned += earned
                        total_max += max_score

    if not subjects:
        return None, "❌ لم يتم العثور على درجات المواد. تأكد من رقم الجلوس."

    total_percent = round((total_earned / total_max) * 100, 2) if total_max > 0 else 0

    if total_percent >= 90:
        grade = "ممتاز"
    elif total_percent >= 80:
        grade = "جيد جداً"
    elif total_percent >= 65:
        grade = "جيد"
    elif total_percent >= 50:
        grade = "مقبول"
    else:
        grade = "ضعيف"

    result = {
        "name": name,
        "seat": seat,
        "section": section,
        "edu_type": edu_type,
        "raw_grade": raw_grade,
        "total_earned": round(total_earned, 2),
        "total_max": round(total_max, 2),
        "total_percent": total_percent,
        "grade": grade,
        "subjects": subjects,
    }
    return result, None

def get_cached_or_fetch(seat):
    global total_requests
    total_requests += 1

    now = datetime.now()
    if seat in cache:
        result, timestamp = cache[seat]
        if now - timestamp < timedelta(seconds=CACHE_DURATION):
            return result, None
        else:
            del cache[seat]

    result, error = get_student_data(seat)
    if error:
        return None, error
    cache[seat] = (result, now)
    return result, None

def register_user(user_id):
    users_set.add(user_id)

def result_buttons(seat):
    markup = InlineKeyboardMarkup(row_width=2)
    btn_new = InlineKeyboardButton("🔄 بحث جديد", callback_data="new_search")
    btn_share = InlineKeyboardButton("📤 مشاركة", switch_inline_query=f"نتيجة الطالب {seat}")
    btn_home = InlineKeyboardButton("🏠 الرئيسية", callback_data="home")
    markup.add(btn_new, btn_share, btn_home)
    return markup

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ===== أوامر البوت =====

@bot.message_handler(commands=['start'])
def start_cmd(message):
    if not ensure_subscription(message):
        return
    user_id = message.from_user.id
    register_user(user_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("ℹ️ التعليمات", callback_data="help"))
    bot.reply_to(
        message,
        "🎓 أهلاً بك في بوت نتيجة الثانوية العامة!\n\n"
        "أرسل رقم الجلوس (أرقام فقط) وسأجلب لك النتيجة.\n"
        "مثال: 1776500",
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    if not ensure_subscription(message):
        return
    user_id = message.from_user.id
    register_user(user_id)
    bot.reply_to(
        message,
        "📌 **تعليمات البوت:**\n"
        "• أرسل رقم الجلوس (7 أرقام) لعرض النتيجة.\n"
        "• ستظهر لك الأزرار لإعادة البحث أو المشاركة.\n"
        "• النتيجة تُخزن مؤقتاً لمدة ساعة لتسريع الاستعلام.\n"
        "• في حال حدوث خطأ، حاول مرة أخرى لاحقاً.\n\n"
        "للتواصل: @goo_cker"
    )

# ===== أوامر المطور =====
@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    if not ensure_subscription(message):
        return
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ غير مصرح لك بهذا الأمر.")
        return
    uptime = datetime.now() - start_time
    stats = (
        f"📊 **إحصائيات البوت**\n"
        f"👥 عدد المستخدمين: {len(users_set)}\n"
        f"📦 حجم الكاش: {len(cache)} مفاتيح\n"
        f"📥 عدد الطلبات: {total_requests}\n"
        f"⏳ مدة التشغيل: {str(uptime).split('.')[0]}\n"
        f"🕒 وقت بدء التشغيل: {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    bot.reply_to(message, stats)

@bot.message_handler(commands=['clear_cache'])
def clear_cache_cmd(message):
    if not ensure_subscription(message):
        return
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ غير مصرح لك بهذا الأمر.")
        return
    cache.clear()
    bot.reply_to(message, "✅ تم مسح الكاش بنجاح.")

@bot.message_handler(commands=['users'])
def users_cmd(message):
    if not ensure_subscription(message):
        return
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ غير مصرح لك بهذا الأمر.")
        return
    if not users_set:
        bot.reply_to(message, "لا يوجد مستخدمون مسجلون بعد.")
        return
    user_list = list(users_set)[:50]
    text = "👥 قائمة المستخدمين (أول 50):\n" + "\n".join(str(uid) for uid in user_list)
    if len(users_set) > 50:
        text += f"\n... و {len(users_set) - 50} آخرين"
    bot.reply_to(message, text)

@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(message):
    if not ensure_subscription(message):
        return
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ غير مصرح لك بهذا الأمر.")
        return
    msg = bot.reply_to(message, "✏️ أرسل النص الذي تريد بثه لجميع المستخدمين:")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    if not ensure_subscription(message):
        return
    if not is_admin(message.from_user.id):
        return
    text = message.text
    if not text:
        bot.reply_to(message, "❌ النص فارغ، تم الإلغاء.")
        return

    sent_count = 0
    fail_count = 0
    for uid in users_set:
        try:
            bot.send_message(uid, f"📢 **إعلان من المطور:**\n{text}")
            sent_count += 1
            time.sleep(0.05)
        except Exception:
            fail_count += 1
    bot.reply_to(message, f"✅ تم إرسال البث إلى {sent_count} مستخدم.\n❌ فشل في {fail_count} مستخدم.")

# ===== معالجة الأزرار =====
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id

    # التعامل مع خطوات الاشتراك
    if call.data == "sub_telegram":
        # بعد الضغط على تم الاشتراك في التليجرام
        if get_sub_step(user_id) != 'telegram':
            bot.answer_callback_query(call.id, "⚠️ يرجى اتباع الخطوات بالترتيب.")
            return
        # نعدل الرسالة الحالية إلى الخطوة التالية
        bot.edit_message_text(
            "🔒 **الخطوة 2 من 2:**\n\n"
            "• اضغط على زر **اشترك في واتساب** واشترك في القناة.\n"
            "• ثم اضغط على **تم الاشتراك في واتساب** لتفعيل البوت.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("💬 اشترك في واتساب", url=CHANNEL_WHATSAPP),
            InlineKeyboardButton("✅ تم الاشتراك في واتساب", callback_data="sub_whatsapp")
        )
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        set_sub_step(user_id, 'whatsapp')
        bot.answer_callback_query(call.id, "✅ تم، انتقل للخطوة التالية")
        return

    elif call.data == "sub_whatsapp":
        if get_sub_step(user_id) != 'whatsapp':
            bot.answer_callback_query(call.id, "⚠️ يرجى اتباع الخطوات بالترتيب.")
            return
        # نعدل الرسالة إلى التفعيل النهائي
        bot.edit_message_text(
            "✅ **تهانينا!**\n\n"
            "لقد أكملت جميع خطوات الاشتراك.\n"
            "اضغط على **تفعيل البوت الآن** لبدء الاستخدام.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 تفعيل البوت الآن", callback_data="activate_bot"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        set_sub_step(user_id, 'ready')
        bot.answer_callback_query(call.id, "✅ تم، اضغط على تفعيل البوت")
        return

    elif call.data == "activate_bot":
        if get_sub_step(user_id) != 'ready':
            bot.answer_callback_query(call.id, "⚠️ يجب إكمال الخطوات أولاً.")
            return
        # تسجيل المستخدم كمشترك
        mark_subscribed(user_id)
        bot.edit_message_text(
            "🎉 **تم تفعيل البوت بنجاح!**\n\n"
            "يمكنك الآن إرسال رقم الجلوس (7 أرقام) للحصول على النتيجة.\n"
            "استخدم /help للتعليمات.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        # إزالة الأزرار
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "✅ البوت مفعل الآن!")
        # نستدعي start_cmd ليعرض رسالة الترحيب
        start_cmd(call.message)
        return

    # باقي الأزرار تحتاج اشتراك
    if not ensure_subscription(call.message):
        return

    register_user(user_id)

    if call.data == "new_search":
        bot.answer_callback_query(call.id, "أرسل رقم الجلوس الجديد")
        bot.send_message(call.message.chat.id, "✏️ أرسل رقم الجلوس (أرقام فقط):")
    elif call.data == "home":
        bot.answer_callback_query(call.id)
        start_cmd(call.message)
    elif call.data == "help":
        bot.answer_callback_query(call.id)
        help_cmd(call.message)
    else:
        bot.answer_callback_query(call.id, "خيار غير معروف")

# ===== معالجة الأرقام =====
@bot.message_handler(func=lambda m: re.match(r"^\d+$", m.text))
def handle_seat(message):
    if not ensure_subscription(message):
        return

    user_id = message.from_user.id
    register_user(user_id)

    seat = message.text.strip()
    if len(seat) != 7:
        bot.reply_to(message, "❌ رقم الجلوس يجب أن يكون 7 أرقام. حاول مرة أخرى.")
        return

    msg = bot.reply_to(message, "⏳ جاري جلب النتيجة...")

    result, error = get_cached_or_fetch(seat)
    if error:
        bot.edit_message_text(error, chat_id=message.chat.id, message_id=msg.message_id)
        return

    subjects_lines = []
    for subj, info in result["subjects"].items():
        subjects_lines.append(f"📘 {subj}: {info['earned']} / {info['max']}  ({info['percent']}%)")

    subjects_text = "\n".join(subjects_lines) if subjects_lines else "لا توجد مواد"

    reply = (
        f"🎓 **نتيجة الطالب**\n"
        f"👤 **الاسم:** {result['name']}\n"
        f"🆔 **رقم الجلوس:** {result['seat']}\n"
        f"📚 **الشعبة:** {result['section']}\n"
        f"🏫 **نوع التعليم:** {result['edu_type']}\n"
        f"📊 **المجموع:** {result['total_earned']} / {result['total_max']}\n"
        f"📈 **النسبة المئوية:** {result['total_percent']}%\n"
        f"🏅 **التقدير:** {result['grade']}\n"
        f"📌 **تقدير الموقع:** {result['raw_grade']}\n\n"
        f"📋 **تفاصيل الدرجات:**\n{subjects_text}"
    )

    bot.edit_message_text(
        reply,
        chat_id=message.chat.id,
        message_id=msg.message_id,
        parse_mode="Markdown",
        reply_markup=result_buttons(seat)
    )

# ===== معالجة الرسائل الأخرى =====
@bot.message_handler(func=lambda m: True)
def handle_other(message):
    if not ensure_subscription(message):
        return
    user_id = message.from_user.id
    register_user(user_id)
    bot.reply_to(message, "❌ يرجى إرسال رقم الجلوس (أرقام فقط) أو استخدم /help للتعليمات.")

# ===== تشغيل البوت =====
if __name__ == "__main__":
    print("🤖 البوت شغال مع نظام اشتراك تسلسلي")
    bot.infinity_polling()
