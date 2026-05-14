"""
بوت مكتبة الجامعة - نظام متكامل لإدارة الملفات الدراسية
المطور: Abduljbbar AL_Qdasi
"""

import sqlite3
import os
import json
import re
from datetime import datetime, timedelta
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import pandas as pd

# ============= الإعدادات =============
TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "8825417900:AAGQ_6i5nk6XpUglRuypiXGTUbrHm2fmZC0")
OWNER_ID = int(os.environ.get("OWNER_ID", "1812586002"))
GROUP_ID = int(os.environ.get("GROUP_ID", "-1003709487288"))  # قناة البوت
CHANNEL_LINK = "https://t.me/+2GOhgqO8jLVlM2Y0"
DEVELOPER    = "Abduljbbar AL_Qdasi"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "university_bot.db")
ADMINS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admins.json")
DAILY_MSG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daily_msg.json")
HTML = "HTML"

CATEGORIES  = ["محاضرات", "ملازم", "واجبات", "اختبارات سابقة", "مشاريع"]
CAT_EMOJIS  = ["📝", "📋", "✏️", "📊", "🗂"]

# ============= صلاحيات الأدمن =============
PERMISSIONS = ["addjob", "deljob", "viewjobs", "editdaily", "delfile", "admin"]


def load_admins():
    """تحميل قائمة الأدمن من ملف JSON"""
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_admins(admins):
    """حفظ قائمة الأدمن في ملف JSON"""
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(admins, f, ensure_ascii=False, indent=2)


def has_permission(user_id, perm):
    """التحقق من صلاحية المستخدم"""
    if user_id == OWNER_ID:
        return True
    admins = load_admins()
    user_adm = admins.get(str(user_id))
    if user_adm and user_adm.get(perm, False):
        return True
    return False


# ============= إدارة الرسائل اليومية =============
def load_daily_msg():
    """تحميل إعدادات الرسالة اليومية"""
    if os.path.exists(DAILY_MSG_FILE):
        with open(DAILY_MSG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"enabled": False, "time": "09:00", "text": ""}


def save_daily_msg(data):
    """حفظ إعدادات الرسالة اليومية"""
    with open(DAILY_MSG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def send_daily_message(context: ContextTypes.DEFAULT_TYPE):
    """إرسال الرسالة اليومية المجدولة"""
    daily = load_daily_msg()
    if daily.get("enabled") and daily.get("text"):
        try:
            await context.bot.send_message(chat_id=GROUP_ID, text=daily["text"], parse_mode=HTML)
        except Exception as e:
            print(f"خطأ في إرسال الرسالة اليومية: {e}")


def setup_daily_job(context: ContextTypes.DEFAULT_TYPE):
    """إعداد المهمة اليومية في job_queue"""
    daily = load_daily_msg()
    if daily.get("enabled") and daily.get("time"):
        try:
            # حذف المهمة القديمة إن وجدت
            current_jobs = context.job_queue.jobs()
            for job in current_jobs:
                if job.name == "daily_message":
                    job.schedule_removal()
            
            # إنشاء مهمة جديدة
            time_str = daily["time"]
            hour, minute = map(int, time_str.split(":"))
            context.job_queue.run_daily(
                send_daily_message,
                time=datetime.time(datetime.now().replace(hour=hour, minute=minute, second=0)),
                days=tuple(range(7)),
                name="daily_message"
            )
        except Exception as e:
            print(f"خطأ في إعداد المهمة اليومية: {e}")


# ============= دوال مساعدة للمواعيد =============
def parse_weekly_job(data: str):
    """تحليل موعد أسبوعي: 0 21:00 نص"""
    pattern = r'^(\d)\s+(\d{1,2}:\d{2})\s+(.+)$'
    match = re.match(pattern, data.strip())
    if match:
        day = int(match.group(1))
        time_str = match.group(2)
        text = match.group(3)
        return day, time_str, text
    return None


def parse_once_job(data: str):
    """تحليل موعد لمرة واحدة: 2026-10-20 21:00 نص"""
    pattern = r'^(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})\s+(.+)$'
    match = re.match(pattern, data.strip())
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        text = match.group(3)
        return date_str, time_str, text
    return None


def day_name(day_num):
    """تحويل رقم اليوم إلى اسم"""
    days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    return days[day_num] if 0 <= day_num <= 6 else "غير معروف"


def h(text: object) -> str:
    """تهريب النص لـ HTML"""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ====================================================================
#  قاعدة البيانات
# ====================================================================
SEED_DATA = {
    ("🛡", "أمن سيبراني"): {
        "المستوى 1": [
            "مقدمة في الأمن السيبراني", "التصميم المنطقي الرقمي", "برمجة C++",
            "مقدمة للحاسبات", "لغة إنجليزية 1", "لغة عربية 1",
            "تفاضل وتكامل", "جبر خطي", "ثقافة إسلامية", "أخلاقيات الحاسوب"
        ],
        "المستوى 2": [
            "هياكل البيانات والخوارزميات", "شبكات الحاسوب 1", "نظم قواعد البيانات",
            "أمنية المعلومات", "البرمجة كائنية التوجه", "أساسيات تقنيات الويب",
            "إدارة وصيانة الأنظمة", "تحليل وتصميم الخوارزميات", "احتمالات وإحصاء"
        ],
        "المستوى 3": [
            "أمن الشبكات", "التشفير", "إدارة مشاريع تقنية المعلومات",
            "البرمجة المرنة", "الذكاء الاصطناعي", "أمن قواعد البيانات",
            "اختبار الاختراق", "أمن التطبيقات", "تحليل الفيروسات"
        ],
        "المستوى 4": [
            "أمن سحابي", "الحوسبة الجنائية", "أمن إنترنت الأشياء",
            "إدارة المخاطر الأمنية", "سياسات الأمن السيبراني",
            "مشروع التخرج", "أمن الهواتف الذكية", "الهندسة الاجتماعية"
        ],
    },
    ("💻", "علوم حاسوب"): {
        "المستوى 1": [
            "مقدمة في علوم الحاسوب", "برمجة 1", "رياضيات متقطعة",
            "لغة إنجليزية", "لغة عربية", "تفاضل وتكامل", "جبر خطي", "ثقافة إسلامية"
        ],
        "المستوى 2": [
            "هياكل البيانات", "برمجة 2", "نظم تشغيل", "شبكات",
            "قواعد بيانات", "تحليل عددي", "احتمالات", "هندسة برمجيات"
        ],
        "المستوى 3": [
            "خوارزميات متقدمة", "برمجة ويب", "أمن معلومات",
            "ذكاء اصطناعي", "رسوميات حاسوب", "لغات برمجة", "مناهج بحث"
        ],
        "المستوى 4": [
            "تطوير تطبيقات", "حوسبة سحابية", "تحليل بيانات",
            "مشروع تخرج", "أخلاقيات مهنية", "إنترنت الأشياء"
        ],
    },
    ("🖥", "تقنية معلومات"): {
        "المستوى 1": [
            "مقدمة في تقنية المعلومات", "مهارات حاسوبية", "إنجليزي تقني",
            "لغة عربية", "رياضيات", "فيزياء", "مهارات تواصل"
        ],
        "المستوى 2": [
            "برمجة ويب", "قواعد بيانات", "شبكات حاسوب", "نظم تشغيل",
            "تحليل نظم", "إدارة مشاريع", "أمن معلومات"
        ],
        "المستوى 3": [
            "برمجة تطبيقات", "تطوير نظم", "ذكاء أعمال",
            "تجارة إلكترونية", "وسائط multimedia", "إدارة خوادم", "أمن شبكات"
        ],
        "المستوى 4": [
            "حوسبة سحابية", "تحليل بيانات كبير", "إدارة تقنية",
            "مشروع تخرج", "جودة برمجيات", "أخلاقيات تقنية"
        ],
    },
}


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_database():
    conn = get_conn()
    c = conn.cursor()

    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT, first_name TEXT, last_name TEXT,
        join_date TEXT, last_active TEXT, is_blocked INTEGER DEFAULT 0
    )''')

    # جداول الأقسام الديناميكية
    c.execute('''CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emoji TEXT DEFAULT "🏛",
        name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level_id INTEGER NOT NULL REFERENCES levels(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    )''')

    # جدول الملفات (مرتبط بـ IDs الديناميكية)
    c.execute('''CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_id INTEGER, level_id INTEGER, subject_id INTEGER,
        cat_idx INTEGER,
        file_name TEXT, telegram_file_id TEXT,
        file_size INTEGER, uploaded_by INTEGER, upload_date TEXT
    )''')

    # جدول السجلات
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, action TEXT, details TEXT, timestamp TEXT
    )''')

    conn.commit()

    # زرع البيانات الأولية إن لم تكن موجودة
    c.execute("SELECT COUNT(*) FROM departments")
    if c.fetchone()[0] == 0:
        sort_d = 0
        for (emoji, dept_name), levels_dict in SEED_DATA.items():
            c.execute("INSERT INTO departments (emoji, name, sort_order) VALUES (?,?,?)",
                      (emoji, dept_name, sort_d))
            dept_id = c.lastrowid
            sort_d += 1
            sort_l = 0
            for level_name, subjects_list in levels_dict.items():
                c.execute("INSERT INTO levels (dept_id, name, sort_order) VALUES (?,?,?)",
                          (dept_id, level_name, sort_l))
                level_id = c.lastrowid
                sort_l += 1
                for sort_s, subj_name in enumerate(subjects_list):
                    c.execute("INSERT INTO subjects (level_id, name, sort_order) VALUES (?,?,?)",
                              (level_id, subj_name, sort_s))
        conn.commit()

    conn.close()


def log_sync(user_id, action, details=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO logs (user_id, action, details, timestamp) VALUES (?,?,?,?)",
        (user_id, action, details, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def update_user_sync(user_id, username, first_name, last_name=""):
    conn = get_conn()
    now = datetime.now().isoformat()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if c.fetchone():
        conn.execute(
            "UPDATE users SET username=?,first_name=?,last_name=?,last_active=? WHERE user_id=?",
            (username, first_name, last_name, now, user_id)
        )
    else:
        conn.execute(
            "INSERT INTO users (user_id,username,first_name,last_name,join_date,last_active,is_blocked) VALUES (?,?,?,?,?,?,0)",
            (user_id, username, first_name, last_name, now, now)
        )
    conn.commit()
    conn.close()


# ====================================================================
#  دوال استعلام قاعدة البيانات
# ====================================================================
def db_departments():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, emoji, name FROM departments ORDER BY sort_order, id"
    ).fetchall()
    conn.close()
    return rows  # [(id, emoji, name), ...]


def db_levels(dept_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name FROM levels WHERE dept_id=? ORDER BY sort_order, id", (dept_id,)
    ).fetchall()
    conn.close()
    return rows


def db_subjects(level_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name FROM subjects WHERE level_id=? ORDER BY sort_order, id", (level_id,)
    ).fetchall()
    conn.close()
    return rows


def db_dept(dept_id):
    conn = get_conn()
    row = conn.execute("SELECT id,emoji,name FROM departments WHERE id=?", (dept_id,)).fetchone()
    conn.close()
    return row


def db_level(level_id):
    conn = get_conn()
    row = conn.execute("SELECT id,name,dept_id FROM levels WHERE id=?", (level_id,)).fetchone()
    conn.close()
    return row


def db_subject(subj_id):
    conn = get_conn()
    row = conn.execute("SELECT id,name,level_id FROM subjects WHERE id=?", (subj_id,)).fetchone()
    conn.close()
    return row


def db_swap_order(table, id1, id2):
    """تبادل ترتيب صفين"""
    conn = get_conn()
    o1 = conn.execute(f"SELECT sort_order FROM {table} WHERE id=?", (id1,)).fetchone()[0]
    o2 = conn.execute(f"SELECT sort_order FROM {table} WHERE id=?", (id2,)).fetchone()[0]
    conn.execute(f"UPDATE {table} SET sort_order=? WHERE id=?", (o2, id1))
    conn.execute(f"UPDATE {table} SET sort_order=? WHERE id=?", (o1, id2))
    conn.commit()
    conn.close()


# ====================================================================
#  لوحات المفاتيح — تصفح ورفع
# ====================================================================
def main_keyboard(user_id):
    kb = [
        [InlineKeyboardButton("📚 تصفح المكتبة",  callback_data="browse")],
        [InlineKeyboardButton("📤 رفع ملف",        callback_data="upload")],
        [InlineKeyboardButton("📢 قناة المكتبة",   url=CHANNEL_LINK)],
    ]
    if user_id == OWNER_ID or has_permission(user_id, "admin"):
        kb.append([InlineKeyboardButton("👑 لوحة الأدمن", callback_data="admin")])
    return InlineKeyboardMarkup(kb)


def departments_keyboard(mode="b"):
    """mode: b=تصفح  u=رفع"""
    depts = db_departments()
    kb = []
    for did, emoji, name in depts:
        kb.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f"{mode}D{did}")])
    kb.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="main")])
    return InlineKeyboardMarkup(kb)


def levels_keyboard(dept_id, mode="b"):
    levels = db_levels(dept_id)
    kb = []
    for lid, name in levels:
        kb.append([InlineKeyboardButton(f"📚 {name}", callback_data=f"{mode}L{dept_id}_{lid}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{mode}dept")])
    return InlineKeyboardMarkup(kb)


def subjects_keyboard(dept_id, level_id, mode="b"):
    subjs = db_subjects(level_id)
    kb = []
    for sid, name in subjs:
        kb.append([InlineKeyboardButton(f"📖 {name}", callback_data=f"{mode}S{dept_id}_{level_id}_{sid}")])
    kb.append([
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{mode}D{dept_id}"),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="main"),
    ])
    return InlineKeyboardMarkup(kb)


def categories_keyboard(dept_id, level_id, subj_id, mode="b"):
    kb = []
    for ci, cat in enumerate(CATEGORIES):
        kb.append([InlineKeyboardButton(f"{CAT_EMOJIS[ci]} {cat}",
                                        callback_data=f"{mode}C{dept_id}_{level_id}_{subj_id}_{ci}")])
    kb.append([
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{mode}L{dept_id}_{level_id}"),
        InlineKeyboardButton("🏠 الرئيسية", callback_data="main"),
    ])
    return InlineKeyboardMarkup(kb)


def files_view_keyboard(dept_id, level_id, subj_id, ci):
    kb = [
        [InlineKeyboardButton("📤 إضافة ملف لهذا القسم",
                              callback_data=f"uC{dept_id}_{level_id}_{subj_id}_{ci}")],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data=f"bS{dept_id}_{level_id}_{subj_id}"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main"),
        ],
    ]
    return InlineKeyboardMarkup(kb)


# ====================================================================
#  لوحات المفاتيح — إدارة الأدمن
# ====================================================================
def admin_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 المستخدمون",        callback_data="adm_users")],
        [InlineKeyboardButton("📁 إدارة الملفات (حذف)", callback_data="adm_manage_files")],
        [InlineKeyboardButton("📋 السجلات الأخيرة",   callback_data="adm_logs")],
        [InlineKeyboardButton("📊 تصدير Excel",        callback_data="adm_excel")],
        [InlineKeyboardButton("⚙️ إدارة الأقسام",     callback_data="adm_depts")],
        [InlineKeyboardButton("🔙 الرئيسية",           callback_data="main")],
    ])

def adm_files_manage_keyboard(page=0):
    conn = get_conn()
    # جلب 10 ملفات حسب الصفحة
    files = conn.execute(
        "SELECT id, file_name FROM files ORDER BY id DESC LIMIT 10 OFFSET ?", 
        (page * 10,)
    ).fetchall()
    conn.close()
    
    kb = []
    for fid, fname in files:
        kb.append([
            InlineKeyboardButton(f"📄 {fname[:25]}", callback_data="none"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"adm_fdel_{fid}_{page}")
        ])
    
    # أزرار التنقل
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"adm_fpage_{page-1}"))
    if len(files) == 10:
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"adm_fpage_{page+1}"))
    if nav: kb.append(nav)
    
    kb.append([InlineKeyboardButton("🔙 رجوع لوحة الأدمن", callback_data="admin")])
    return InlineKeyboardMarkup(kb)


def adm_depts_keyboard():
    depts = db_departments()
    kb = []
    for i, (did, emoji, name) in enumerate(depts):
        row = [InlineKeyboardButton(f"{emoji} {name}", callback_data=f"adm_dep_{did}")]
        if i > 0:
            row.append(InlineKeyboardButton("⬆️", callback_data=f"adm_dup_{did}"))
        if i < len(depts) - 1:
            row.append(InlineKeyboardButton("⬇️", callback_data=f"adm_ddn_{did}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="adm_dadd")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin")])
    return InlineKeyboardMarkup(kb)


def adm_dept_detail_keyboard(dept_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تعديل الاسم",     callback_data=f"adm_dedit_{dept_id}")],
        [InlineKeyboardButton("🔤 تغيير الإيموجي",  callback_data=f"adm_demoji_{dept_id}")],
        [InlineKeyboardButton("📚 إدارة المستويات", callback_data=f"adm_levels_{dept_id}")],
        [InlineKeyboardButton("🗑 حذف القسم",       callback_data=f"adm_ddel_{dept_id}")],
        [InlineKeyboardButton("🔙 رجوع",            callback_data="adm_depts")],
    ])


def adm_levels_keyboard(dept_id):
    levels = db_levels(dept_id)
    kb = []
    for i, (lid, name) in enumerate(levels):
        row = [InlineKeyboardButton(f"📚 {name}", callback_data=f"adm_lev_{dept_id}_{lid}")]
        if i > 0:
            row.append(InlineKeyboardButton("⬆️", callback_data=f"adm_lup_{dept_id}_{lid}"))
        if i < len(levels) - 1:
            row.append(InlineKeyboardButton("⬇️", callback_data=f"adm_ldn_{dept_id}_{lid}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("➕ إضافة مستوى", callback_data=f"adm_ladd_{dept_id}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_dep_{dept_id}")])
    return InlineKeyboardMarkup(kb)


def adm_level_detail_keyboard(dept_id, level_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تعديل الاسم",      callback_data=f"adm_ledit_{dept_id}_{level_id}")],
        [InlineKeyboardButton("📖 إدارة المواد",      callback_data=f"adm_subjs_{dept_id}_{level_id}")],
        [InlineKeyboardButton("🗑 حذف المستوى",       callback_data=f"adm_ldel_{dept_id}_{level_id}")],
        [InlineKeyboardButton("🔙 رجوع",              callback_data=f"adm_levels_{dept_id}")],
    ])


def adm_subjects_keyboard(dept_id, level_id):
    subjs = db_subjects(level_id)
    kb = []
    for i, (sid, name) in enumerate(subjs):
        row = [InlineKeyboardButton(f"📖 {name}", callback_data=f"adm_sub_{dept_id}_{level_id}_{sid}")]
        if i > 0:
            row.append(InlineKeyboardButton("⬆️", callback_data=f"adm_sup_{dept_id}_{level_id}_{sid}"))
        if i < len(subjs) - 1:
            row.append(InlineKeyboardButton("⬇️", callback_data=f"adm_sdn_{dept_id}_{level_id}_{sid}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("➕ إضافة مادة", callback_data=f"adm_sadd_{dept_id}_{level_id}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_lev_{dept_id}_{level_id}")])
    return InlineKeyboardMarkup(kb)


def adm_subject_detail_keyboard(dept_id, level_id, subj_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تعديل الاسم",  callback_data=f"adm_sedit_{dept_id}_{level_id}_{subj_id}")],
        [InlineKeyboardButton("🗑 حذف المادة",    callback_data=f"adm_sdel_{dept_id}_{level_id}_{subj_id}")],
        [InlineKeyboardButton("🔙 رجوع",          callback_data=f"adm_subjs_{dept_id}_{level_id}")],
    ])


def confirm_keyboard(yes_cb, no_cb):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، احذف", callback_data=yes_cb),
         InlineKeyboardButton("❌ لا، رجوع", callback_data=no_cb)],
    ])


# ====================================================================
#  أوامر الأدمن الجديدة
# ====================================================================
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة أدمن جديد مع أزرار لاختيار الصلاحيات"""
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("❌ فقط المالك يمكنه إضافة أدمن جدد.")
        return
    
    if not context.args:
        await update.message.reply_text("📌 الاستخدام: `/addadmin 123456789`", parse_mode=HTML)
        return
    
    try:
        new_admin_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال معرف صحيح (أرقام فقط).")
        return
    
    if new_admin_id == OWNER_ID:
        await update.message.reply_text("👑 المالك لديه جميع الصلاحيات بشكل تلقائي.")
        return
    
    # حفظ المعرف مؤقتاً في context.user_data
    context.user_data["pending_admin"] = new_admin_id
    
    # إنشاء أزرار الصلاحيات
    kb = []
    for perm in PERMISSIONS:
        kb.append([InlineKeyboardButton(f"➕ {perm}", callback_data=f"adm_perm_add_{perm}")])
    kb.append([InlineKeyboardButton("✅ إنهاء وإضافة", callback_data="adm_perm_done")])
    kb.append([InlineKeyboardButton("❌ إلغاء", callback_data="adm_perm_cancel")])
    
    await update.message.reply_text(
        f"➕ إضافة أدمن جديد: <code>{new_admin_id}</code>\n\n"
        "اختر الصلاحيات التي تريد منحها (يمكنك اختيار عدة صلاحيات):\n\n"
        "• <b>addjob</b> - إضافة مواعيد جديدة\n"
        "• <b>deljob</b> - حذف المواعيد\n"
        "• <b>viewjobs</b> - عرض المواعيد\n"
        "• <b>editdaily</b> - تعديل الرسالة اليومية\n"
        "• <b>delfile</b> - حذف الملفات\n"
        "• <b>admin</b> - دخول لوحة الأدمن\n\n"
        "بعد اختيار الصلاحيات، اضغط 'إنهاء وإضافة'",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=HTML
    )


async def addjob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة موعد أسبوعي: /addjob 0 21:00 نص الرسالة"""
    user = update.effective_user
    if not has_permission(user.id, "addjob"):
        await update.message.reply_text("❌ ما عندك صلاحية لإضافة مواعيد.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📌 الاستخدام: `/addjob 0 21:00 نص الرسالة`\n\n"
            "• اليوم: 0=الاثنين, 1=الثلاثاء, ..., 6=الأحد\n"
            "• الوقت: 21:00 (تنسيق 24 ساعة)\n"
            "• النص: أي رسالة تريد إرسالها",
            parse_mode=HTML
        )
        return
    
    args_str = " ".join(context.args)
    result = parse_weekly_job(args_str)
    
    if not result:
        await update.message.reply_text(
            "❌ صيغة غير صحيحة.\n"
            "الصيغة الصحيحة: `/addjob 0 21:00 نص الرسالة`\n"
            "مثال: `/addjob 2 15:30 تذكير: اجتمع مع الفريق`",
            parse_mode=HTML
        )
        return
    
    day, time_str, text = result
    
    # إضافة المهمة إلى job_queue
    try:
        hour, minute = map(int, time_str.split(":"))
        
        # إنشاء دالة الإرسال
        async def send_job_message(context: ContextTypes.DEFAULT_TYPE):
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode=HTML)
            except Exception as e:
                print(f"خطأ في إرسال الرسالة المجدولة: {e}")
        
        # جدولة المهمة الأسبوعية
        job = context.job_queue.run_daily(
            send_job_message,
            time=datetime.time(datetime.now().replace(hour=hour, minute=minute, second=0)),
            days=(day,),
            name=f"weekly_{day}_{time_str}_{datetime.now().timestamp()}"
        )
        
        # حفظ المهمة في user_data لتتبعها
        if "jobs_list" not in context.bot_data:
            context.bot_data["jobs_list"] = []
        context.bot_data["jobs_list"].append({
            "type": "weekly",
            "day": day,
            "time": time_str,
            "text": text,
            "job_name": job.name
        })
        
        await update.message.reply_text(
            f"✅ تم إضافة الموعد الأسبوعي بنجاح!\n\n"
            f"📅 اليوم: {day_name(day)}\n"
            f"⏰ الوقت: {time_str}\n"
            f"📝 النص: {text[:100]}{'...' if len(text) > 100 else ''}",
            parse_mode=HTML
        )
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {e}")


async def oncejob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة موعد لمرة واحدة: /oncejob 2026-10-20 21:00 نص الرسالة"""
    user = update.effective_user
    if not has_permission(user.id, "addjob"):
        await update.message.reply_text("❌ ما عندك صلاحية لإضافة مواعيد.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📌 الاستخدام: `/oncejob 2026-10-20 21:00 نص الرسالة`\n\n"
            "• التاريخ: 2026-10-20 (صيغة سنة-شهر-يوم)\n"
            "• الوقت: 21:00 (تنسيق 24 ساعة)\n"
            "• النص: أي رسالة تريد إرسالها",
            parse_mode=HTML
        )
        return
    
    args_str = " ".join(context.args)
    result = parse_once_job(args_str)
    
    if not result:
        await update.message.reply_text(
            "❌ صيغة غير صحيحة.\n"
            "الصيغة الصحيحة: `/oncejob 2026-10-20 21:00 نص الرسالة`\n"
            "مثال: `/oncejob 2026-12-25 09:00 عطلة رسمية`",
            parse_mode=HTML
        )
        return
    
    date_str, time_str, text = result
    
    try:
        target_date = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if target_date < datetime.now():
            await update.message.reply_text("❌ لا يمكن جدولة موعد في الماضي.")
            return
        
        # إنشاء دالة الإرسال
        async def send_once_message(context: ContextTypes.DEFAULT_TYPE):
            try:
                await context.bot.send_message(chat_id=GROUP_ID, text=text, parse_mode=HTML)
            except Exception as e:
                print(f"خطأ في إرسال الرسالة لمرة واحدة: {e}")
        
        # جدولة المهمة لمرة واحدة
        job = context.job_queue.run_once(
            send_once_message,
            when=target_date,
            name=f"once_{date_str}_{time_str}_{datetime.now().timestamp()}"
        )
        
        # حفظ المهمة
        if "jobs_list" not in context.bot_data:
            context.bot_data["jobs_list"] = []
        context.bot_data["jobs_list"].append({
            "type": "once",
            "date": date_str,
            "time": time_str,
            "text": text,
            "job_name": job.name
        })
        
        await update.message.reply_text(
            f"✅ تم إضافة الموعد (مرة واحدة) بنجاح!\n\n"
            f"📅 التاريخ: {date_str}\n"
            f"⏰ الوقت: {time_str}\n"
            f"📝 النص: {text[:100]}{'...' if len(text) > 100 else ''}",
            parse_mode=HTML
        )
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {e}")


async def setdaily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعديل الرسالة اليومية: /setdaily 09:00 نص الرسالة"""
    user = update.effective_user
    if not has_permission(user.id, "editdaily"):
        await update.message.reply_text("❌ ما عندك صلاحية لتعديل الرسالة اليومية.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📌 الاستخدام: `/setdaily 09:00 نص الرسالة`\n\n"
            "• الوقت: 09:00 (تنسيق 24 ساعة)\n"
            "• النص: أي رسالة تريد إرسالها يومياً",
            parse_mode=HTML
        )
        return
    
    args_str = " ".join(context.args)
    pattern = r'^(\d{1,2}:\d{2})\s+(.+)$'
    match = re.match(pattern, args_str.strip())
    
    if not match:
        await update.message.reply_text(
            "❌ صيغة غير صحيحة.\n"
            "الصيغة الصحيحة: `/setdaily 09:00 نص الرسالة`\n"
            "مثال: `/setdaily 20:00 تذكير: لا تنسوا مراجعة المواد`",
            parse_mode=HTML
        )
        return
    
    time_str, text = match.groups()
    
    # حفظ في ملف JSON
    daily_data = {
        "enabled": True,
        "time": time_str,
        "text": text
    }
    save_daily_msg(daily_data)
    
    # إعادة تشغيل المهمة اليومية
    setup_daily_job(context)
    
    await update.message.reply_text(
        f"✅ تم تحديث الرسالة اليومية!\n\n"
        f"⏰ الوقت: {time_str}\n"
        f"📝 النص: {text[:200]}{'...' if len(text) > 200 else ''}",
        parse_mode=HTML
    )


async def deljob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف موعد معين: /deljob اسم_الجدول"""
    user = update.effective_user
    if not has_permission(user.id, "deljob"):
        await update.message.reply_text("❌ ما عندك صلاحية لحذف المواعيد.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📌 الاستخدام: `/deljob job_name`\n\n"
            "لعرض قائمة المواعيد النشطة، استخدم /listjobs",
            parse_mode=HTML
        )
        return
    
    job_name = " ".join(context.args)
    
    # البحث عن المهمة وإزالتها
    removed = False
    if "jobs_list" in context.bot_data:
        for i, job_info in enumerate(context.bot_data["jobs_list"]):
            if job_info.get("job_name") == job_name:
                # إزالة المهمة من job_queue
                current_jobs = context.job_queue.jobs()
                for job in current_jobs:
                    if job.name == job_name:
                        job.schedule_removal()
                        removed = True
                        break
                # حذف من القائمة
                context.bot_data["jobs_list"].pop(i)
                break
    
    if removed:
        await update.message.reply_text(f"✅ تم حذف الموعد: `{job_name}`", parse_mode=HTML)
    else:
        await update.message.reply_text(f"❌ لم يتم العثور على موعد بهذا الاسم: `{job_name}`", parse_mode=HTML)


async def delday_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف كل مواعيد يوم معين: /delday 6 (6=الأحد)"""
    user = update.effective_user
    if not has_permission(user.id, "deljob"):
        await update.message.reply_text("❌ ما عندك صلاحية لحذف المواعيد.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📌 الاستخدام: `/delday 0`\n\n"
            "• 0=الاثنين, 1=الثلاثاء, 2=الأربعاء, 3=الخميس\n"
            "• 4=الجمعة, 5=السبت, 6=الأحد",
            parse_mode=HTML
        )
        return
    
    try:
        day_num = int(context.args[0])
        if day_num < 0 or day_num > 6:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم يوم صحيح بين 0 و 6.")
        return
    
    # البحث عن المواعيد في هذا اليوم وحذفها
    removed_count = 0
    if "jobs_list" in context.bot_data:
        jobs_to_remove = []
        for i, job_info in enumerate(context.bot_data["jobs_list"]):
            if job_info.get("type") == "weekly" and job_info.get("day") == day_num:
                jobs_to_remove.append((i, job_info.get("job_name")))
        
        # حذف من الخلف لتجنب مشاكل الفهرسة
        for i, job_name in reversed(jobs_to_remove):
            # إزالة من job_queue
            current_jobs = context.job_queue.jobs()
            for job in current_jobs:
                if job.name == job_name:
                    job.schedule_removal()
                    removed_count += 1
                    break
            # حذف من القائمة
            context.bot_data["jobs_list"].pop(i)
    
    if removed_count > 0:
        await update.message.reply_text(f"✅ تم حذف {removed_count} موعد/مواعيد ليوم {day_name(day_num)}.")
    else:
        await update.message.reply_text(f"❌ لا توجد مواعيد ليوم {day_name(day_num)}.")


async def listjobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض كل المواعيد النشطة"""
    user = update.effective_user
    if not has_permission(user.id, "viewjobs"):
        await update.message.reply_text("❌ ما عندك صلاحية لعرض المواعيد.")
        return
    
    if "jobs_list" not in context.bot_data or not context.bot_data["jobs_list"]:
        await update.message.reply_text("📭 لا توجد مواعيد نشطة حالياً.")
        return
    
    lines = ["📋 **المواعيد النشطة:**\n"]
    for job_info in context.bot_data["jobs_list"]:
        if job_info["type"] == "weekly":
            lines.append(
                f"🔄 أسبوعي | {day_name(job_info['day'])} | {job_info['time']}\n"
                f"   📝 {job_info['text'][:50]}...\n"
                f"   🆔 `{job_info['job_name']}`\n"
            )
        else:
            lines.append(
                f"⏰ لمرة واحدة | {job_info['date']} {job_info['time']}\n"
                f"   📝 {job_info['text'][:50]}...\n"
                f"   🆔 `{job_info['job_name']}`\n"
            )
    
    await update.message.reply_text("\n".join(lines), parse_mode=HTML)


# ====================================================================
#  المعالجات الرئيسية
# ====================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user_sync(user.id, user.username or "", user.first_name, user.last_name or "")
    log_sync(user.id, "start")

    text = (
        f"🎓 <b>أهلاً وسهلاً {h(user.first_name)}!</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📚 <b>مكتبة الجامعة الرقمية</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "يمكنك من خلال هذا البوت:\n"
        "• 🔍 تصفح المواد الدراسية لجميع الأقسام\n"
        "• 📥 تحميل الملفات (محاضرات، ملازم، واجبات...)\n"
        "• 📤 رفع ومشاركة ملفاتك مع زملائك\n\n"
        "📢 انضم لقناتنا (اختياري):\n"
        f"{CHANNEL_LINK}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 <b>المطور:</b> {h(DEVELOPER)}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard(user.id), parse_mode=HTML)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = update.effective_user
    data  = query.data

    update_user_sync(user.id, user.username or "", user.first_name, user.last_name or "")

    # ── معالجة أزرار إضافة الأدمن ──
    if data.startswith("adm_perm_"):
        if user.id != OWNER_ID:
            await query.answer("❌ فقط المالك يمكنه إضافة أدمن.", show_alert=True)
            return
        
        pending = context.user_data.get("pending_admin")
        if not pending:
            await query.edit_message_text("❌ انتهت الجلسة، يرجى إعادة المحاولة.")
            return
        
        if data == "adm_perm_cancel":
            context.user_data.pop("pending_admin", None)
            await query.edit_message_text("❌ تم إلغاء إضافة الأدمن.")
            return
        
        if data == "adm_perm_done":
            admins = load_admins()
            user_adm = admins.get(str(pending), {})
            admins[str(pending)] = user_adm
            save_admins(admins)
            context.user_data.pop("pending_admin", None)
            await query.edit_message_text(f"✅ تم إضافة المستخدم <code>{pending}</code> كأدمن بنجاح!", parse_mode=HTML)
            return
        
        # إضافة صلاحية
        perm = data.replace("adm_perm_add_", "")
        if perm in PERMISSIONS:
            admins = load_admins()
            if str(pending) not in admins:
                admins[str(pending)] = {}
            admins[str(pending)][perm] = True
            save_admins(admins)
            
            # تحديث القائمة
            kb = []
            for p in PERMISSIONS:
                if admins[str(pending)].get(p, False):
                    kb.append([InlineKeyboardButton(f"✅ {p}", callback_data=f"adm_perm_add_{p}")])
                else:
                    kb.append([InlineKeyboardButton(f"➕ {p}", callback_data=f"adm_perm_add_{p}")])
            kb.append([InlineKeyboardButton("✅ إنهاء وإضافة", callback_data="adm_perm_done")])
            kb.append([InlineKeyboardButton("❌ إلغاء", callback_data="adm_perm_cancel")])
            
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
            await query.answer(f"✅ تم إضافة صلاحية {perm}")
        return

    # ── الرئيسية ──
    if data == "main":
        context.user_data.clear()
        await query.edit_message_text(
            "🎓 <b>القائمة الرئيسية</b>", reply_markup=main_keyboard(user.id), parse_mode=HTML
        )
        return

    # ── تصفح ──
    if data == "browse":
        context.user_data.clear()
        await query.edit_message_text("🏛 <b>اختر القسم:</b>",
                                      reply_markup=departments_keyboard("b"), parse_mode=HTML)
        return

    # ── رفع ──
    if data == "upload":
        context.user_data.clear()
        await query.edit_message_text("📤 <b>رفع ملف — اختر القسم:</b>",
                                      reply_markup=departments_keyboard("u"), parse_mode=HTML)
        return

    # ── رجوع للأقسام ──
    if data in ("bdept", "udept"):
        mode = data[0]
        txt = "📤 <b>رفع ملف — اختر القسم:</b>" if mode == "u" else "🏛 <b>اختر القسم:</b>"
        await query.edit_message_text(txt, reply_markup=departments_keyboard(mode), parse_mode=HTML)
        return

    # ── اختيار قسم ──
    if data.startswith("bD") or data.startswith("uD"):
        mode, dept_id = data[0], int(data[2:])
        dept = db_dept(dept_id)
        if not dept:
            await query.edit_message_text("❌ القسم غير موجود.", reply_markup=main_keyboard(user.id), parse_mode=HTML)
            return
        _, emoji, name = dept
        prefix = "📤 <b>رفع ملف — " if mode == "u" else ""
        suffix = "</b>" if mode == "u" else ""
        await query.edit_message_text(
            f"{emoji} <b>{h(name)}</b>{suffix}\n\nاختر المستوى:",
            reply_markup=levels_keyboard(dept_id, mode), parse_mode=HTML
        )
        return

    # ── اختيار مستوى ──
    if (data.startswith("bL") or data.startswith("uL")) and data.count("_") == 1:
        mode = data[0]
        parts = data[2:].split("_")
        dept_id, level_id = int(parts[0]), int(parts[1])
        dept  = db_dept(dept_id)
        level = db_level(level_id)
        if not dept or not level:
            await query.edit_message_text("❌ البيانات غير موجودة.", parse_mode=HTML)
            return
        _, emoji, dname = dept
        _, lname, _ = level
        await query.edit_message_text(
            f"{emoji} <b>{h(dname)} | {h(lname)}</b>\n\nاختر المادة:",
            reply_markup=subjects_keyboard(dept_id, level_id, mode), parse_mode=HTML
        )
        return

    # ── اختيار مادة ──
    if (data.startswith("bS") or data.startswith("uS")) and "_" in data:
        mode = data[0]
        parts = data[2:].split("_")
        dept_id, level_id, subj_id = int(parts[0]), int(parts[1]), int(parts[2])
        subj = db_subject(subj_id)
        if not subj:
            await query.edit_message_text("❌ المادة غير موجودة.", parse_mode=HTML)
            return
        _, sname, _ = subj
        await query.edit_message_text(
            f"📖 <b>{h(sname)}</b>\n\nاختر نوع الملف:",
            reply_markup=categories_keyboard(dept_id, level_id, subj_id, mode), parse_mode=HTML
        )
        return

    # ── عرض الملفات ──
    if data.startswith("bC") and "_" in data:
        parts = data[2:].split("_")
        dept_id, level_id, subj_id, ci = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        subj = db_subject(subj_id)
        sname = subj[1] if subj else "؟"
        cat   = CATEGORIES[ci]
        log_sync(user.id, "browse", f"{sname}-{cat}")

        conn = get_conn()
        files = conn.execute(
            "SELECT file_name, telegram_file_id FROM files WHERE dept_id=? AND level_id=? AND subject_id=? AND cat_idx=?",
            (dept_id, level_id, subj_id, ci)
        ).fetchall()
        conn.close()

        if files:
            await query.edit_message_text(
                f"📂 <b>{h(sname)} | {h(cat)}</b>\n\n✅ يوجد <b>{len(files)}</b> ملف، جاري الإرسال...",
                reply_markup=files_view_keyboard(dept_id, level_id, subj_id, ci), parse_mode=HTML
            )
            for fname, fid in files:
                try:
                    await context.bot.send_document(chat_id=user.id, document=fid,
                                                    caption=f"📄 {fname}\n📂 {sname} | {cat}")
                except Exception:
                    await query.message.reply_text(f"⚠️ تعذّر إرسال: {fname}")
        else:
            await query.edit_message_text(
                f"📂 <b>{h(sname)} | {h(cat)}</b>\n\n❌ لا توجد ملفات بعد.\n\nكن أول من يساهم! 👇",
                reply_markup=files_view_keyboard(dept_id, level_id, subj_id, ci), parse_mode=HTML
            )
        return

    # ── رجوع لقائمة المواد (من صفحة عرض الملفات، مع 3 شرطات) ──
    if data.startswith("bL") and data.count("_") == 2:
        parts = data[2:].split("_")
        dept_id, level_id = int(parts[0]), int(parts[1])
        dept  = db_dept(dept_id)
        level = db_level(level_id)
        _, emoji, dname = dept or (0, "🏛", "؟")
        _, lname, _     = level or (0, "؟", 0)
        await query.edit_message_text(
            f"{emoji} <b>{h(dname)} | {h(lname)}</b>\n\nاختر المادة:",
            reply_markup=subjects_keyboard(dept_id, level_id, "b"), parse_mode=HTML
        )
        return

    # ── إضافة ملف مباشرةً لقسم محدد ──
    if data.startswith("uC") and "_" in data:
        parts = data[2:].split("_")
        dept_id, level_id, subj_id, ci = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        subj  = db_subject(subj_id)
        dept  = db_dept(dept_id)
        level = db_level(level_id)
        sname = subj[1]  if subj  else "؟"
        dname = dept[2]  if dept  else "؟"
        lname = level[1] if level else "؟"
        cat   = CATEGORIES[ci]

        context.user_data.update({
            "awaiting_file": True,
            "dept_id": dept_id, "level_id": level_id,
            "subj_id": subj_id, "ci": ci,
        })
        await query.edit_message_text(
            f"📤 <b>رفع ملف</b>\n\n"
            f"📂 {h(dname)} ‹ {h(lname)} ‹ {h(sname)} ‹ {h(cat)}\n\n"
            "✅ أرسل الملف الآن:", parse_mode=HTML
        )
        return

    # ==================================================================
    #  لوحة الأدمن
    # ==================================================================
    if user.id != OWNER_ID and not has_permission(user.id, "admin"):
        return  # تجاهل أي callback أدمن من غير الأدمن

    if data == "admin":
        await _admin_main(query)
        return

    # إدارة حذف الملفات
    if data == "adm_manage_files":
        if not has_permission(user.id, "delfile"):
            await query.edit_message_text("❌ ما عندك صلاحية لإدارة الملفات.", parse_mode=HTML)
            return
        await query.edit_message_text("📁 **إدارة الملفات:**\nاختر الملف الذي تريد حذفه:", 
                                     reply_markup=adm_files_manage_keyboard(0), parse_mode=HTML)
        return

    if data.startswith("adm_fpage_"):
        if not has_permission(user.id, "delfile"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        page = int(data.split("_")[-1])
        await query.edit_message_text("📁 **إدارة الملفات:**", 
                                     reply_markup=adm_files_manage_keyboard(page), parse_mode=HTML)
        return

    if data.startswith("adm_fdel_"):
        if not has_permission(user.id, "delfile"):
            await query.answer("❌ ما عندك صلاحية لحذف الملفات.", show_alert=True)
            return
        parts = data.split("_")
        fid, page = int(parts[2]), int(parts[3])
        conn = get_conn()
        conn.execute("DELETE FROM files WHERE id=?", (fid,))
        conn.commit()
        conn.close()
        await query.answer("✅ تم حذف الملف بنجاح")
        await query.edit_message_text("📁 **إدارة الملفات:**", 
                                     reply_markup=adm_files_manage_keyboard(page), parse_mode=HTML)
        return

    if data == "adm_users":
        await _adm_users(query)
        return

    if data == "adm_logs":
        await _adm_logs(query)
        return

    if data == "adm_files":
        await _adm_files(query)
        return

    if data == "adm_excel":
        await _adm_excel(query, context, user.id)
        return

    # ── قائمة الأقسام ──
    if data == "adm_depts":
        if not has_permission(user.id, "admin"):
            await query.edit_message_text("❌ ما عندك صلاحية لإدارة الأقسام.", parse_mode=HTML)
            return
        await query.edit_message_text(
            "⚙️ <b>إدارة الأقسام</b>\n\nاضغط على قسم لتعديله أو استخدم الأسهم لإعادة الترتيب:",
            reply_markup=adm_depts_keyboard(), parse_mode=HTML
        )
        return

    # ── تفاصيل قسم ──
    if data.startswith("adm_dep_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        dept_id = int(data.split("_")[-1])
        dept = db_dept(dept_id)
        if not dept:
            await query.answer("القسم غير موجود!", show_alert=True)
            return
        _, emoji, name = dept
        await query.edit_message_text(
            f"{emoji} <b>{h(name)}</b>\n\nماذا تريد أن تفعل؟",
            reply_markup=adm_dept_detail_keyboard(dept_id), parse_mode=HTML
        )
        return

    # ── تعديل اسم القسم ──
    if data.startswith("adm_dedit_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        dept_id = int(data.split("_")[-1])
        context.user_data["admin_action"] = "edit_dept"
        context.user_data["admin_target"]  = dept_id
        dept = db_dept(dept_id)
        await query.edit_message_text(
            f"✏️ أرسل الاسم الجديد للقسم <b>{h(dept[2]) if dept else ''}</b>:",
            parse_mode=HTML
        )
        return

    # ── تغيير إيموجي القسم ──
    if data.startswith("adm_demoji_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        dept_id = int(data.split("_")[-1])
        context.user_data["admin_action"] = "edit_dept_emoji"
        context.user_data["admin_target"]  = dept_id
        await query.edit_message_text("🔤 أرسل الإيموجي الجديد للقسم:", parse_mode=HTML)
        return

    # ── إضافة قسم ──
    if data == "adm_dadd":
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        context.user_data["admin_action"] = "add_dept"
        await query.edit_message_text(
            "➕ أرسل اسم القسم الجديد:\n(سيُضاف بإيموجي 🏛 افتراضي، يمكنك تغييره لاحقاً)", parse_mode=HTML
        )
        return

    # ── حذف قسم (تأكيد) ──
    if data.startswith("adm_ddel_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        dept_id = int(data.split("_")[-1])
        dept = db_dept(dept_id)
        name = dept[2] if dept else "؟"
        await query.edit_message_text(
            f"⚠️ هل أنت متأكد من حذف قسم <b>{h(name)}</b> وجميع ما فيه؟",
            reply_markup=confirm_keyboard(f"adm_ddelok_{dept_id}", f"adm_dep_{dept_id}"),
            parse_mode=HTML
        )
        return

    # ── تأكيد الحذف ──
    if data.startswith("adm_ddelok_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        dept_id = int(data.split("_")[-1])
        conn = get_conn()
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM departments WHERE id=?", (dept_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(
            "✅ تم حذف القسم.", reply_markup=adm_depts_keyboard(), parse_mode=HTML
        )
        return

    # ── تحريك قسم للأعلى / الأسفل ──
    if data.startswith("adm_dup_") or data.startswith("adm_ddn_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        dept_id  = int(data.split("_")[-1])
        depts    = db_departments()
        ids      = [r[0] for r in depts]
        idx      = ids.index(dept_id) if dept_id in ids else -1
        if data.startswith("adm_dup_") and idx > 0:
            db_swap_order("departments", dept_id, ids[idx - 1])
        elif data.startswith("adm_ddn_") and 0 <= idx < len(ids) - 1:
            db_swap_order("departments", dept_id, ids[idx + 1])
        await query.edit_message_text(
            "⚙️ <b>إدارة الأقسام</b>",
            reply_markup=adm_depts_keyboard(), parse_mode=HTML
        )
        return

    # ── قائمة المستويات ──
    if data.startswith("adm_levels_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        dept_id = int(data.split("_")[-1])
        dept = db_dept(dept_id)
        name = dept[2] if dept else "؟"
        await query.edit_message_text(
            f"📚 <b>مستويات {h(name)}</b>:",
            reply_markup=adm_levels_keyboard(dept_id), parse_mode=HTML
        )
        return

    # ── تفاصيل مستوى ──
    if data.startswith("adm_lev_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[8:].split("_")
        dept_id, level_id = int(parts[0]), int(parts[1])
        level = db_level(level_id)
        name = level[1] if level else "؟"
        await query.edit_message_text(
            f"📚 <b>{h(name)}</b>\n\nماذا تريد؟",
            reply_markup=adm_level_detail_keyboard(dept_id, level_id), parse_mode=HTML
        )
        return

    # ── تعديل اسم مستوى ──
    if data.startswith("adm_ledit_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[10:].split("_")
        dept_id, level_id = int(parts[0]), int(parts[1])
        context.user_data.update({"admin_action": "edit_level", "admin_target": level_id, "admin_dept": dept_id})
        level = db_level(level_id)
        await query.edit_message_text(
            f"✏️ أرسل الاسم الجديد للمستوى <b>{h(level[1]) if level else ''}</b>:", parse_mode=HTML
        )
        return

    # ── إضافة مستوى ──
    if data.startswith("adm_ladd_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        dept_id = int(data.split("_")[-1])
        context.user_data.update({"admin_action": "add_level", "admin_target": dept_id})
        await query.edit_message_text("➕ أرسل اسم المستوى الجديد:", parse_mode=HTML)
        return

    # ── حذف مستوى ──
    if data.startswith("adm_ldel_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[9:].split("_")
        dept_id, level_id = int(parts[0]), int(parts[1])
        level = db_level(level_id)
        name = level[1] if level else "؟"
        await query.edit_message_text(
            f"⚠️ حذف المستوى <b>{h(name)}</b> وجميع مواده؟",
            reply_markup=confirm_keyboard(f"adm_ldelok_{dept_id}_{level_id}", f"adm_lev_{dept_id}_{level_id}"),
            parse_mode=HTML
        )
        return

    if data.startswith("adm_ldelok_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[11:].split("_")
        dept_id, level_id = int(parts[0]), int(parts[1])
        conn = get_conn()
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM levels WHERE id=?", (level_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(
            "✅ تم حذف المستوى.",
            reply_markup=adm_levels_keyboard(dept_id), parse_mode=HTML
        )
        return

    # ── تحريك مستوى ──
    if data.startswith("adm_lup_") or data.startswith("adm_ldn_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[8:].split("_")
        dept_id, level_id = int(parts[0]), int(parts[1])
        levels = db_levels(dept_id)
        ids    = [r[0] for r in levels]
        idx    = ids.index(level_id) if level_id in ids else -1
        if data.startswith("adm_lup_") and idx > 0:
            db_swap_order("levels", level_id, ids[idx - 1])
        elif data.startswith("adm_ldn_") and 0 <= idx < len(ids) - 1:
            db_swap_order("levels", level_id, ids[idx + 1])
        dept = db_dept(dept_id)
        name = dept[2] if dept else "؟"
        await query.edit_message_text(
            f"📚 <b>مستويات {h(name)}</b>:",
            reply_markup=adm_levels_keyboard(dept_id), parse_mode=HTML
        )
        return

    # ── قائمة المواد ──
    if data.startswith("adm_subjs_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[10:].split("_")
        dept_id, level_id = int(parts[0]), int(parts[1])
        level = db_level(level_id)
        name = level[1] if level else "؟"
        await query.edit_message_text(
            f"📖 <b>مواد {h(name)}</b>:",
            reply_markup=adm_subjects_keyboard(dept_id, level_id), parse_mode=HTML
        )
        return

    # ── تفاصيل مادة ──
    if data.startswith("adm_sub_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[8:].split("_")
        dept_id, level_id, subj_id = int(parts[0]), int(parts[1]), int(parts[2])
        subj = db_subject(subj_id)
        name = subj[1] if subj else "؟"
        await query.edit_message_text(
            f"📖 <b>{h(name)}</b>\n\nماذا تريد؟",
            reply_markup=adm_subject_detail_keyboard(dept_id, level_id, subj_id), parse_mode=HTML
        )
        return

    # ── تعديل اسم مادة ──
    if data.startswith("adm_sedit_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[10:].split("_")
        dept_id, level_id, subj_id = int(parts[0]), int(parts[1]), int(parts[2])
        context.user_data.update({
            "admin_action": "edit_subject",
            "admin_target": subj_id,
            "admin_dept": dept_id, "admin_level": level_id
        })
        subj = db_subject(subj_id)
        await query.edit_message_text(
            f"✏️ أرسل الاسم الجديد للمادة <b>{h(subj[1]) if subj else ''}</b>:", parse_mode=HTML
        )
        return

    # ── إضافة مادة ──
    if data.startswith("adm_sadd_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[9:].split("_")
        dept_id, level_id = int(parts[0]), int(parts[1])
        context.user_data.update({
            "admin_action": "add_subject",
            "admin_target": level_id,
            "admin_dept": dept_id, "admin_level": level_id
        })
        await query.edit_message_text("➕ أرسل اسم المادة الجديدة:", parse_mode=HTML)
        return

    # ── حذف مادة ──
    if data.startswith("adm_sdel_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[9:].split("_")
        dept_id, level_id, subj_id = int(parts[0]), int(parts[1]), int(parts[2])
        subj = db_subject(subj_id)
        name = subj[1] if subj else "؟"
        await query.edit_message_text(
            f"⚠️ حذف المادة <b>{h(name)}</b>؟",
            reply_markup=confirm_keyboard(
                f"adm_sdelok_{dept_id}_{level_id}_{subj_id}",
                f"adm_sub_{dept_id}_{level_id}_{subj_id}"
            ), parse_mode=HTML
        )
        return

    if data.startswith("adm_sdelok_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[11:].split("_")
        dept_id, level_id, subj_id = int(parts[0]), int(parts[1]), int(parts[2])
        conn = get_conn()
        conn.execute("DELETE FROM subjects WHERE id=?", (subj_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(
            "✅ تم حذف المادة.",
            reply_markup=adm_subjects_keyboard(dept_id, level_id), parse_mode=HTML
        )
        return

    # ── تحريك مادة ──
    if data.startswith("adm_sup_") or data.startswith("adm_sdn_"):
        if not has_permission(user.id, "admin"):
            await query.answer("❌ ما عندك صلاحية.", show_alert=True)
            return
        parts = data[8:].split("_")
        dept_id, level_id, subj_id = int(parts[0]), int(parts[1]), int(parts[2])
        subjs = db_subjects(level_id)
        ids   = [r[0] for r in subjs]
        idx   = ids.index(subj_id) if subj_id in ids else -1
        if data.startswith("adm_sup_") and idx > 0:
            db_swap_order("subjects", subj_id, ids[idx - 1])
        elif data.startswith("adm_sdn_") and 0 <= idx < len(ids) - 1:
            db_swap_order("subjects", subj_id, ids[idx + 1])
        level = db_level(level_id)
        name = level[1] if level else "؟"
        await query.edit_message_text(
            f"📖 <b>مواد {h(name)}</b>:",
            reply_markup=adm_subjects_keyboard(dept_id, level_id), parse_mode=HTML
        )
        return


# ====================================================================
#  إحصائيات الأدمن
# ====================================================================
async def _admin_main(query):
    conn = get_conn()
    total_users  = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    blocked      = conn.execute("SELECT COUNT(*) FROM users WHERE is_blocked=1").fetchone()[0]
    day_ago      = (datetime.now() - timedelta(hours=24)).isoformat()
    week_ago     = (datetime.now() - timedelta(days=7)).isoformat()
    active_24h   = conn.execute("SELECT COUNT(*) FROM users WHERE last_active>?", (day_ago,)).fetchone()[0]
    new_week     = conn.execute("SELECT COUNT(*) FROM users WHERE join_date>?",   (week_ago,)).fetchone()[0]
    total_files  = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    total_logs   = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    logs_24h     = conn.execute("SELECT COUNT(*) FROM logs WHERE timestamp>?",    (day_ago,)).fetchone()[0]
    total_depts  = conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
    conn.close()

    text = (
        "👑 <b>لوحة تحكم الأدمن</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 <b>المستخدمون:</b>\n"
        f"• الإجمالي: <code>{total_users}</code>  |  نشطاء 24h: <code>{active_24h}</code>\n"
        f"• هذا الأسبوع: <code>{new_week}</code>  |  محظورون: <code>{blocked}</code>\n\n"
        "📁 <b>الملفات:</b> <code>{}</code>\n"
        "🏛 <b>الأقسام:</b> <code>{}</code>\n\n"
        "📋 <b>السجلات:</b> إجمالي <code>{}</code>  |  24h: <code>{}</code>"
    ).format(total_files, total_depts, total_logs, logs_24h)

    await query.edit_message_text(text, reply_markup=admin_main_keyboard(), parse_mode=HTML)


async def _adm_users(query):
    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id,first_name,username,join_date,last_active FROM users ORDER BY join_date DESC LIMIT 15"
    ).fetchall()
    conn.close()
    lines = ["👥 <b>آخر 15 مستخدم:</b>\n"]
    for uid, fname, uname, jd, la in rows:
        lines.append(
            f"• <b>{h(fname or '')}</b> (@{h(uname or '—')})\n"
            f"  🆔 <code>{uid}</code> | انضم: {(jd or '')[:10]} | نشط: {(la or '')[:10]}"
        )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin")]])
    await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode=HTML)


async def _adm_logs(query):
    conn = get_conn()
    rows = conn.execute(
        "SELECT l.user_id,u.first_name,l.action,l.timestamp "
        "FROM logs l LEFT JOIN users u ON l.user_id=u.user_id "
        "ORDER BY l.timestamp DESC LIMIT 20"
    ).fetchall()
    conn.close()
    labels = {"start": "▶️ بدأ", "browse": "🔍 تصفّح", "upload_file": "📤 رفع", "click": "👆 ضغط"}
    lines = ["📋 <b>آخر 20 نشاط:</b>\n"]
    for uid, fname, action, ts in rows:
        lines.append(f"• {h(fname or str(uid))} | {labels.get(action, action)} | {(ts or '')[11:16]}")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin")]])
    await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode=HTML)


async def _adm_files(query):
    conn = get_conn()
    rows = conn.execute(
        "SELECT f.file_name,d.name,s.name,f.cat_idx,f.upload_date "
        "FROM files f "
        "LEFT JOIN departments d ON f.dept_id=d.id "
        "LEFT JOIN subjects s ON f.subject_id=s.id "
        "ORDER BY f.upload_date DESC LIMIT 20"
    ).fetchall()
    conn.close()
    if not rows:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin")]])
        await query.edit_message_text("📁 لا توجد ملفات.", reply_markup=kb, parse_mode=HTML)
        return
    lines = ["📁 <b>آخر 20 ملف:</b>\n"]
    for fname, dname, sname, ci, udate in rows:
        cat = CATEGORIES[ci] if ci is not None and 0 <= ci < len(CATEGORIES) else "؟"
        lines.append(f"• <b>{h(fname)}</b> | {h(dname or '؟')} | {h(sname or '؟')} | {h(cat)} | {(udate or '')[:10]}")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin")]])
    await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode=HTML)


async def _adm_excel(query, context, user_id):
    await query.edit_message_text("⏳ جاري التصدير...")
    conn = get_conn()
    users_df = pd.read_sql_query("SELECT * FROM users", conn)
    logs_df  = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 2000", conn)
    files_df = pd.read_sql_query(
        "SELECT f.*,d.name dept_name,l.name level_name,s.name subject_name "
        "FROM files f "
        "LEFT JOIN departments d ON f.dept_id=d.id "
        "LEFT JOIN levels l ON f.level_id=l.id "
        "LEFT JOIN subjects s ON f.subject_id=s.id", conn
    )
    depts_df = pd.read_sql_query(
        "SELECT d.emoji,d.name dept,l.name level_name,s.name subject "
        "FROM departments d "
        "LEFT JOIN levels l ON l.dept_id=d.id "
        "LEFT JOIN subjects s ON s.level_id=l.id "
        "ORDER BY d.sort_order,l.sort_order,s.sort_order", conn
    )
    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        users_df.to_excel(writer, sheet_name="المستخدمين", index=False)
        logs_df.to_excel(writer,  sheet_name="السجلات",    index=False)
        files_df.to_excel(writer, sheet_name="الملفات",    index=False)
        depts_df.to_excel(writer, sheet_name="هيكل الأقسام", index=False)
    output.seek(0)

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin")]])
    await query.edit_message_text("✅ جاري إرسال الملف...", reply_markup=kb)
    await context.bot.send_document(
        chat_id=user_id,
        document=output,
        filename=f"library_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        caption=f"📊 تقرير المكتبة\n👨‍💻 {DEVELOPER}"
    )


# ====================================================================
#  معالج الرسائل النصية (إدارة الأدمن + رفع الملفات)
# ====================================================================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    ud      = context.user_data
    action  = ud.get("admin_action")

    # ── إدارة الأدمن: إدخال نص ──
    if action and (user.id == OWNER_ID or has_permission(user.id, "admin")):
        text = (update.message.text or "").strip()
        if not text:
            await update.message.reply_text("❌ يرجى إرسال نص غير فارغ.")
            return

        conn = get_conn()
        if action == "add_dept":
            conn.execute("INSERT INTO departments (emoji,name,sort_order) VALUES ('🏛',?,?)",
                         (text, 999))
            conn.commit()
            await update.message.reply_text(f"✅ تمت إضافة قسم: <b>{h(text)}</b>",
                                            parse_mode=HTML, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ إدارة الأقسام", callback_data="adm_depts")]]))

        elif action == "edit_dept":
            conn.execute("UPDATE departments SET name=? WHERE id=?", (text, ud["admin_target"]))
            conn.commit()
            await update.message.reply_text(f"✅ تم تعديل اسم القسم إلى: <b>{h(text)}</b>",
                                            parse_mode=HTML, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ إدارة الأقسام", callback_data="adm_depts")]]))

        elif action == "edit_dept_emoji":
            conn.execute("UPDATE departments SET emoji=? WHERE id=?", (text, ud["admin_target"]))
            conn.commit()
            await update.message.reply_text(f"✅ تم تغيير الإيموجي إلى: {h(text)}",
                                            parse_mode=HTML, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ إدارة الأقسام", callback_data="adm_depts")]]))

        elif action == "add_level":
            dept_id = ud["admin_target"]
            conn.execute("INSERT INTO levels (dept_id,name,sort_order) VALUES (?,?,999)", (dept_id, text))
            conn.commit()
            await update.message.reply_text(f"✅ تمت إضافة مستوى: <b>{h(text)}</b>",
                                            parse_mode=HTML, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 إدارة المستويات", callback_data=f"adm_levels_{dept_id}")]]))

        elif action == "edit_level":
            conn.execute("UPDATE levels SET name=? WHERE id=?", (text, ud["admin_target"]))
            conn.commit()
            dept_id = ud.get("admin_dept", 0)
            await update.message.reply_text(f"✅ تم تعديل اسم المستوى إلى: <b>{h(text)}</b>",
                                            parse_mode=HTML, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 إدارة المستويات", callback_data=f"adm_levels_{dept_id}")]]))

        elif action == "add_subject":
            level_id = ud["admin_target"]
            dept_id  = ud.get("admin_dept", 0)
            conn.execute("INSERT INTO subjects (level_id,name,sort_order) VALUES (?,?,999)", (level_id, text))
            conn.commit()
            await update.message.reply_text(f"✅ تمت إضافة مادة: <b>{h(text)}</b>",
                                            parse_mode=HTML, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📖 إدارة المواد", callback_data=f"adm_subjs_{dept_id}_{level_id}")]]))

        elif action == "edit_subject":
            conn.execute("UPDATE subjects SET name=? WHERE id=?", (text, ud["admin_target"]))
            conn.commit()
            dept_id  = ud.get("admin_dept", 0)
            level_id = ud.get("admin_level", 0)
            await update.message.reply_text(f"✅ تم تعديل اسم المادة إلى: <b>{h(text)}</b>",
                                            parse_mode=HTML, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📖 إدارة المواد", callback_data=f"adm_subjs_{dept_id}_{level_id}")]]))

        conn.close()
        ud.pop("admin_action", None)
        return

    # ── رفع ملف من المستخدم ──
    if ud.get("awaiting_file"):
        doc   = update.message.document
        photo = update.message.photo
        if not doc and not photo:
            await update.message.reply_text("❌ يرجى إرسال ملف صالح.")
            return

        for key in ("dept_id", "level_id", "subj_id", "ci"):
            if key not in ud:
                await update.message.reply_text("❌ حدث خطأ، ابدأ من جديد /start")
                ud.clear()
                return

        if doc:
            file_name = doc.file_name or f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            file_id   = doc.file_id
            file_size = doc.file_size or 0
        else:
            file      = photo[-1]
            file_name = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            file_id   = file.file_id
            file_size = file.file_size or 0

        dept_id  = ud["dept_id"]
        level_id = ud["level_id"]
        subj_id  = ud["subj_id"]
        ci       = ud["ci"]

        conn = get_conn()
        conn.execute(
            "INSERT INTO files (dept_id,level_id,subject_id,cat_idx,file_name,telegram_file_id,file_size,uploaded_by,upload_date) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (dept_id, level_id, subj_id, ci, file_name, file_id, file_size, user.id, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        subj  = db_subject(subj_id)
        sname = subj[1] if subj else "؟"
        cat   = CATEGORIES[ci]
        log_sync(user.id, "upload_file", f"{sname}-{cat}-{file_name}")

        await update.message.reply_text(
            f"✅ <b>تم رفع الملف بنجاح!</b>\n\n"
            f"📄 <code>{h(file_name)}</code>\n"
            f"📏 {round(file_size/1024,1)} KB\n\n"
            f"📂 {h(sname)} ‹ {h(cat)}\n\n"
            "🙏 شكراً على مساهمتك!",
            parse_mode=HTML, reply_markup=main_keyboard(user.id)
        )
        ud.clear()
        return

    # رسالة غير متوقعة
    await update.message.reply_text(
        "اضغط /start للعودة للقائمة الرئيسية."
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[ERROR] {context.error}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ حدث خطأ، يرجى المحاولة مجدداً أو الضغط على /start"
            )
        except Exception:
            pass


# ====================================================================
#  الدالة الرئيسية
# ====================================================================
def main():
    init_database()
    print("✅ قاعدة البيانات جاهزة")

    app = Application.builder().token(TOKEN).build()
    
    # إضافة معالج الأوامر الجديدة
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addadmin", addadmin_command))
    app.add_handler(CommandHandler("addjob", addjob_command))
    app.add_handler(CommandHandler("oncejob", oncejob_command))
    app.add_handler(CommandHandler("setdaily", setdaily_command))
    app.add_handler(CommandHandler("deljob", deljob_command))
    app.add_handler(CommandHandler("delday", delday_command))
    app.add_handler(CommandHandler("listjobs", listjobs_command))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)

    # إعداد المهمة اليومية عند تشغيل البوت
    setup_daily_job(app)

    print(f"✅ البوت يعمل | المطور: {DEVELOPER}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
