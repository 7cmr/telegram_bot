import os, re, sqlite3
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, ConversationHandler,
    CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)


START, DOCTOR, DATE, TIME, NAME, PHONE = range(6)

DOCTOR_LABELS = {
    "Терапевт": "👨‍⚕️ Терапевт",
    "Стоматолог": "🦷 Стоматолог",
    "Окулист": "👁️ Окулист",
}

def init_db():
    with sqlite3.connect("appointments.db") as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS appointments("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "chat_id INTEGER,"
            "doctor TEXT,"
            "date TEXT,"
            "time TEXT,"
            "name TEXT,"
            "phone TEXT)"
        )
init_db()

load_dotenv("token.env")
TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📝 Записаться", callback_data="begin")]]
    )
    await update.message.reply_text(
        "Здравствуйте! Нажмите «Записаться», чтобы выбрать врача.",
        reply_markup=kb,
    )
    return START

async def begin_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_reply_markup(None)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👨‍⚕️ Терапевт", callback_data="doctor:Терапевт"),
                InlineKeyboardButton("🦷 Стоматолог", callback_data="doctor:Стоматолог"),
            ],
            [
                InlineKeyboardButton("👁️ Окулист", callback_data="doctor:Окулист"),
                InlineKeyboardButton("🔙 Отмена", callback_data="cancel"),
            ],
        ]
    )
    await q.message.reply_text("Выберите специалиста:", reply_markup=kb)
    return DOCTOR

async def doctor_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_reply_markup(None)
    doctor = q.data.split(":", 1)[1]
    context.user_data["doctor"] = doctor
    await q.message.reply_text(f"👨‍⚕️ Вы выбрали: {DOCTOR_LABELS[doctor]}")
    await q.message.reply_text("Введите дату (например, 10.06):")
    return DATE

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text.strip()
    if not re.fullmatch(r"\d{2}\.\d{2}", date_str):
        await update.message.reply_text("Формат должен быть 10.06")
        return DATE
    now = datetime.now()
    try:
        date_obj = datetime.strptime(f"{now.year}.{date_str}", "%Y.%d.%m")
    except ValueError:
        await update.message.reply_text("Такой даты нет, попробуйте ещё раз.")
        return DATE
    if date_obj.date() < now.date():
        await update.message.reply_text("Прошедшая дата недоступна.")
        return DATE
    context.user_data["date"] = date_str
    doctor = context.user_data["doctor"]
    with sqlite3.connect("appointments.db") as c:
        busy = [
            r[0]
            for r in c.execute(
                "SELECT time FROM appointments WHERE doctor=? AND date=?",
                (doctor, date_str),
            )
        ]
    all_slots = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00"]
    free = [t for t in all_slots if t not in busy]
    if not free:
        await update.message.reply_text("На эту дату всё занято. Введите другую дату.")
        return DATE
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(t, callback_data=f"time:{t}")] for t in free]
    )
    await update.message.reply_text("Выберите время:", reply_markup=kb)
    return TIME

async def time_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_reply_markup(None)
    time_sel = q.data.split(":", 1)[1]
    context.user_data["time"] = time_sel
    await q.message.reply_text(f"⏰ Вы выбрали время: {time_sel}")
    await q.message.reply_text("Введите ваше имя:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Введите телефон (можно с +):")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not re.fullmatch(r"\+?\d{10,15}", phone):
        await update.message.reply_text("Неправильный номер, попробуйте ещё раз:")
        return PHONE
    chat_id = update.effective_chat.id
    u = context.user_data
    with sqlite3.connect("appointments.db") as c:
        c.execute(
            "INSERT INTO appointments(chat_id,doctor,date,time,name,phone) "
            "VALUES (?,?,?,?,?,?)",
            (chat_id, u["doctor"], u["date"], u["time"], u["name"], phone),
        )
    text = (
        "✅ Запись подтверждена!\n\n"
        f"{DOCTOR_LABELS[u['doctor']]}\n"
        f"📅 Дата: {u['date']}\n"
        f"⏰ Время: {u['time']}\n"
        f"🙍 Имя: {u['name']}\n"
        f"📞 Телефон: {phone}"
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📝 Записаться снова", callback_data="begin")]]
    )
    await update.message.reply_text(text, reply_markup=kb)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        q = update.callback_query
        await q.answer()
        await q.edit_message_reply_markup(None)
        await q.message.reply_text("Запись отменена. Нажмите /start, чтобы начать заново.")
    else:
        await update.message.reply_text("Запись отменена. Нажмите /start, чтобы начать заново.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(begin_registration, "^begin$"),
        ],
        states={
            START: [CallbackQueryHandler(begin_registration, "^begin$")],
            DOCTOR: [CallbackQueryHandler(doctor_chosen, "^doctor:")],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)],
            TIME: [CallbackQueryHandler(time_chosen, "^time:")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, "^cancel$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
