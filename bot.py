"""
بوت مكتبة الجامعة - نظام متكامل لإدارة الملفات الدراسية
المطور: Abduljbbar AL_Qdasi
"""

import sqlite3
import os
import json
import asyncio
from datetime import datetime, timedelta
from io import BytesIO
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import pandas as pd

# ============= الإعدادات =============
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8825417900:AAGQ_6i5nk6XpUglRuypiXGTUbrHm2fmZC0")
OWNER_ID = int(os.environ.get("OWNER_ID", "1812586002"))
GROUP_ID = -1003709487288  # ID القناة
ADMIN_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admins.json")
DAILY_MSG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daily_msg.json")
SCHEDULE_JOBS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule_jobs.json")

CHANNEL_LINK = "https://t.me/+2GOhgqO8jLVlM2Y0"
DEVELOPER = "Abduljbbar AL_Qdasi"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "university_bot.db")
HTML = "HTML"

CATEGORIES = ["محاضرات", "ملازم", "واجبات", "اختبارات سابقة", "مشاريع"]
CAT_EMOJIS = ["📝", "📋", "✏️", "📊", "🗂"]

# توقيت السعودية (UTC+3)
SAUDI_TZ = pytz.timezone('Asia/Riyadh')

# ============= نظام الصلاحيات =============
def load_admins():
    """تحميل بيانات الأدمن من ملف JSON"""
    if os.path.exists(ADMIN_JSON_PATH):
        with open(ADMIN_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"owner": OWNER_ID, "admins": {}}

def save_admins(admins_data):
    """حفظ بيانات الأدمن إلى ملف JSON"""
    with open(ADMIN_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(admins_data, f, ensure_ascii=False, indent=2)

def has_permission(user_id, permission):
    """التحقق من صلاحية المستخدم"""
    if user_id == OWNER_ID:
        return True
    admins_data = load_admins()
    admin_perms = admins_data.get("admins", {}).get(str(user_id), [])
    return permission in admin_perms

def add_admin(user_id, permissions):
    """إضافة أدمن جديد مع صلاحياته"""
    admins_data = load_admins()
    admins_data["admins"][str(user_id)] = permissions
    save_admins(admins_data)

def remove_admin(user_id):
    """حذف أدمن"""
    admins_data = load_admins()
    if str(user_id) in admins_data["admins"]:
        del admins_data["admins"][str(user_id)]
        save_admins(admins_data)
        return True
    return False

# ============= إدارة الجدولة =============
def load_schedule_jobs():
    """تحميل المهام المجدولة"""
    if os.path.exists(SCHEDULE_JOBS_PATH):
        with open(SCHEDULE_JOBS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"weekly": [], "once": [], "daily": None}

def save_schedule_jobs(jobs_data):
    """حفظ المهام المجدولة"""
    with open(SCHEDULE_JOBS_PATH, 'w', encoding='utf-8') as f:
        json.dump(jobs_data, f, ensure_ascii=False, indent=2)

def load_daily_msg():
    """تحميل رسالة اليومية"""
    if os.path.exists(DAILY_MSG_PATH):
        with open(DAILY_MSG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_daily_msg(time_str, text):
    """حفظ رسالة اليومية"""
    data = {"time": time_str, "text": text, "enabled": True}
    with open(DAILY_MSG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

# أيام الأسبوع
WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

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
    if has_permission(user_id, "admin"):
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


def add_admin_permissions_keyboard(user_id):
    """لوحة اختيار صلاحيات الأدمن"""
    perms = ["addjob", "deljob", "viewjobs", "editdaily", "delfile", "admin"]
    perm_names = {
        "addjob": "➕ إضافة موعد",
        "deljob": "❌ حذف موعد",
        "viewjobs": "👀 عرض المواعيد",
        "editdaily": "✏️ تعديل الرسالة اليومية",
        "delfile": "🗑 حذف الملفات",
        "admin": "👑 أدمن كامل"
    }
    current_perms = load_admins().get("admins", {}).get(str(user_id), [])
    kb = []
    for perm in perms:
        status = "✅" if perm in current_perms else "⬜"
        kb.append([InlineKeyboardButton(f"{status} {perm_names[perm]}", callback_data=f"adm_perm_toggle_{user_id}_{perm}")])
    kb.append([InlineKeyboardButton("✅ تأكيد وحفظ", callback_data=f"adm_perm_save_{user_id}")])
    kb.append([InlineKeyboardButton("🔙 إلغاء", callback_data="admin")])
    return InlineKeyboardMarkup(kb)


def schedule_jobs_keyboard():
    """لوحة عرض المواعيد"""
    jobs_data = load_schedule_jobs()
    kb = []
    if jobs_data.get("daily"):
        kb.append([InlineKeyboardButton("📅 الرسالة اليومية", callback_data="adm_job_daily")])
    for i, job in enumerate(jobs_data.get("weekly", [])):
        kb.append([InlineKeyboardButton(f"📆 أسبوعي: {WEEKDAYS[job['day']]} {job['time']}", callback_data=f"adm_job_weekly_{i}")])
    for i, job in enumerate(jobs_data.get("once", [])):
        kb.append([InlineKeyboardButton(f"⏰ لمرة: {job['datetime']}", callback_data=f"adm_job_once_{i}")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin")])
    return InlineKeyboardMarkup(kb)


# ====================================================================
#  أوامر الجدولة
# ====================================================================
async def addjob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addjob 0 21:00 نص الرسالة : إضافة موعد أسبوعي"""
    user_id = update.effective_user.id
    if not has_permission(user_id, "addjob"):
        await update.message.reply_text("❌ ما عندك صلاحية لإضافة مواعيد.")
        return
    
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "⚠️ الاستخدام:\n/addjob [رقم اليوم] [الوقت] [الرسالة]\n\n"
            "0=الاثنين, 1=الثلاثاء, ..., 6=الأحد\n"
            "مثال: /addjob 0 21:00 مرحباً بكم في المكتبة"
        )
        return
    
    try:
        day = int(args[0])
        if day < 0 or day > 6:
            raise ValueError
        time_str = args[1]
        # التحقق من صيغة الوقت
        datetime.strptime(time_str, "%H:%M")
        message = " ".join(args[2:])
        
        jobs_data = load_schedule_jobs()
        new_job = {
            "day": day,
            "time": time_str,
            "message": message
        }
        jobs_data["weekly"].append(new_job)
        save_schedule_jobs(jobs_data)
        
        await update.message.reply_text(
            f"✅ تم إضافة موعد أسبوعي:\n"
            f"📅 اليوم: {WEEKDAYS[day]}\n"
            f"⏰ الوقت: {time_str}\n"
            f"📝 الرسالة: {message[:50]}..."
        )
    except ValueError:
        await update.message.reply_text("❌ اليوم يجب أن يكون 0-6، والوقت بصيغة HH:MM")


async def oncejob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/oncejob 2026-10-20 21:00 نص الرسالة : إضافة موعد لمرة واحدة"""
    user_id = update.effective_user.id
    if not has_permission(user_id, "addjob"):
        await update.message.reply_text("❌ ما عندك صلاحية لإضافة مواعيد.")
        return
    
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "⚠️ الاستخدام:\n/oncejob [التاريخ] [الوقت] [الرسالة]\n\n"
            "التاريخ بصيغة YYYY-MM-DD\n"
            "مثال: /oncejob 2026-10-20 21:00 اجتماع المكتبة"
        )
        return
    
    try:
        date_str = args[0]
        time_str = args[1]
        datetime_str = f"{date_str} {time_str}"
        # التحقق من الصيغة
        dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        if dt < datetime.now():
            await update.message.reply_text("❌ لا يمكن إضافة موعد في الماضي.")
            return
        message = " ".join(args[2:])
        
        jobs_data = load_schedule_jobs()
        new_job = {
            "datetime": datetime_str,
            "message": message
        }
        jobs_data["once"].append(new_job)
        save_schedule_jobs(jobs_data)
        
        await update.message.reply_text(
            f"✅ تم إضافة موعد لمرة واحدة:\n"
            f"📅 التاريخ: {datetime_str}\n"
            f"📝 الرسالة: {message[:50]}..."
        )
    except ValueError:
        await update.message.reply_text("❌ التاريخ بصيغة YYYY-MM-DD والوقت HH:MM")


async def setdaily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setdaily 09:00 نص الرسالة : تعديل الرسالة اليومية"""
    user_id = update.effective_user.id
    if not has_permission(user_id, "editdaily"):
        await update.message.reply_text("❌ ما عندك صلاحية لتعديل الرسالة اليومية.")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ الاستخدام:\n/setdaily [الوقت] [الرسالة]\n\n"
            "الوقت بصيغة HH:MM\n"
            "مثال: /setdaily 09:00 صباح الخير"
        )
        return
    
    try:
        time_str = args[0]
        datetime.strptime(time_str, "%H:%M")
        message = " ".join(args[1:])
        
        daily_data = save_daily_msg(time_str, message)
        
        await update.message.reply_text(
            f"✅ تم حفظ الرسالة اليومية:\n"
            f"⏰ الوقت: {time_str}\n"
            f"📝 الرسالة: {message[:100]}..."
        )
    except ValueError:
        await update.message.reply_text("❌ الوقت بصيغة HH:MM")


async def deljob_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/deljob اسم_الجدول : حذف موعد معين"""
    user_id = update.effective_user.id
    if not has_permission(user_id, "deljob"):
        await update.message.reply_text("❌ ما عندك صلاحية لحذف المواعيد.")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ الاستخدام:\n"
            "/deljob weekly_0 - لحذف أول موعد أسبوعي\n"
            "/deljob once_0 - لحذف أول موعد لمرة\n"
            "/deljob daily - لحذف الرسالة اليومية\n\n"
            "لعرض قائمة المواعيد استخدم /listjobs"
        )
        return
    
    job_id = args[0]
    jobs_data = load_schedule_jobs()
    
    if job_id == "daily":
        if jobs_data.get("daily"):
            jobs_data["daily"] = None
            if os.path.exists(DAILY_MSG_PATH):
                os.remove(DAILY_MSG_PATH)
            await update.message.reply_text("✅ تم حذف الرسالة اليومية.")
        else:
            await update.message.reply_text("❌ لا توجد رسالة يومية محفوظة.")
    elif job_id.startswith("weekly_"):
        try:
            idx = int(job_id.split("_")[1])
            if 0 <= idx < len(jobs_data.get("weekly", [])):
                removed = jobs_data["weekly"].pop(idx)
                save_schedule_jobs(jobs_data)
                await update.message.reply_text(f"✅ تم حذف الموعد الأسبوعي (اليوم {WEEKDAYS[removed['day']]}).")
            else:
                await update.message.reply_text("❌ الرقم غير صحيح.")
        except (IndexError, ValueError):
            await update.message.reply_text("❌ الرقم غير صحيح. استخدم /listjobs لعرض الأرقام.")
    elif job_id.startswith("once_"):
        try:
            idx = int(job_id.split("_")[1])
            if 0 <= idx < len(jobs_data.get("once", [])):
                removed = jobs_data["once"].pop(idx)
                save_schedule_jobs(jobs_data)
                await update.message.reply_text(f"✅ تم حذف الموعد (التاريخ {removed['datetime']}).")
            else:
                await update.message.reply_text("❌ الرقم غير صحيح.")
        except (IndexError, ValueError):
            await update.message.reply_text("❌ الرقم غير صحيح. استخدم /listjobs لعرض الأرقام.")
    else:
        await update.message.reply_text("❌ الصيغة غير صحيحة. استخدم /listjobs لعرض الأرقام.")


async def delday_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/delday 0 : حذف كل مواعيد يوم معين"""
    user_id = update.effective_user.id
    if not has_permission(user_id, "del):
