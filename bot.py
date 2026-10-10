import os
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
)
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackQueryHandler, ConversationHandler, CallbackContext
)

import config
import database as db
from translations import t, STATUS_TEXT, STATUS_EMOJI, ALL_STATUSES

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Состояния оформления заказа ──
ORDER_SIZE, ORDER_QTY, ORDER_NAME, ORDER_PHONE, ORDER_ADDRESS, ORDER_CONFIRM = range(6)

# ── Состояния добавления товара ──
ADD_CATEGORY, ADD_NAME, ADD_DESC, ADD_PRICE, ADD_MEDIA_TYPE, ADD_MEDIA = range(20, 26)


# ══════════════════════════════════════════
#  ЛОГОТИП — кэшируем file_id после 1-й отправки
# ══════════════════════════════════════════

def send_logo(bot, chat_id: int, caption: str, reply_markup=None):
    """Отправляет логотип магазина. При первом вызове загружает файл и кэширует file_id."""
    if config.LOGO_FILE_ID:
        bot.send_photo(chat_id=chat_id, photo=config.LOGO_FILE_ID,
                       caption=caption, parse_mode="Markdown", reply_markup=reply_markup)
    elif os.path.exists(config.LOGO_PATH):
        with open(config.LOGO_PATH, "rb") as f:
            msg = bot.send_photo(chat_id=chat_id, photo=f,
                                 caption=caption, parse_mode="Markdown",
                                 reply_markup=reply_markup)
        # Кэшируем file_id чтобы не читать файл каждый раз
        config.LOGO_FILE_ID = msg.photo[-1].file_id
    else:
        bot.send_message(chat_id=chat_id, text=caption,
                         parse_mode="Markdown", reply_markup=reply_markup)


# ══════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════

def get_lang(context: CallbackContext, user_id: int = None) -> str:
    lang = context.user_data.get("lang")
    if not lang and user_id:
        lang = db.get_user_lang(user_id)
        if lang:
            context.user_data["lang"] = lang
    return lang or "ru"


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [t(lang, "catalog_btn"),   t(lang, "orders_btn")],
            [t(lang, "how_to_btn"),    t(lang, "delivery_btn")],
            [t(lang, "manager_btn"),   t(lang, "about_btn")],
            [t(lang, "language_btn")],
        ],
        resize_keyboard=True
    )


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский",      callback_data="lang_ru"),
        InlineKeyboardButton("🇦🇿 Azərbaycanca", callback_data="lang_az"),
        InlineKeyboardButton("🇬🇧 English",      callback_data="lang_en"),
    ]])


def is_admin(update: Update) -> bool:
    return update.effective_user.id == config.ADMIN_ID


def send_product_card(bot, chat_id: int, product, lang: str):
    """Отправляет карточку товара с фото/видео/текстом."""
    pid, name, desc, price, photo_id, video_id, media_type = product[:7]
    caption = f"*{name}*\n\n{desc or ''}\n\n💰 {price:.0f} {config.CURRENCY}"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "order_btn"), callback_data=f"order_{pid}"),
    ], [
        InlineKeyboardButton(t(lang, "back_cats_btn"), callback_data="back_to_cats"),
    ]])

    if media_type == "photo" and photo_id:
        bot.send_photo(chat_id=chat_id, photo=photo_id,
                       caption=caption, parse_mode="Markdown", reply_markup=kb)
    elif media_type == "video" and video_id:
        bot.send_video(chat_id=chat_id, video=video_id,
                       caption=caption, parse_mode="Markdown", reply_markup=kb)
    else:
        bot.send_message(chat_id=chat_id, text=caption,
                         parse_mode="Markdown", reply_markup=kb)

    # Логируем просмотр товара
    db.log_event("product_view", chat_id, pid)


# ══════════════════════════════════════════
#  ЯЗЫК
# ══════════════════════════════════════════

def choose_language(update: Update, context: CallbackContext):
    if update.message:
        update.message.reply_text(t("ru", "choose_lang"), reply_markup=lang_kb())
    else:
        update.callback_query.answer()
        update.callback_query.edit_message_text(t("ru", "choose_lang"), reply_markup=lang_kb())


def set_language(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    lang = query.data.split("_")[1]
    context.user_data["lang"] = lang
    db.set_user_lang(query.from_user.id, lang)
    query.delete_message()
    send_logo(
        context.bot,
        chat_id=query.message.chat_id,
        caption=t(lang, "welcome"),
        reply_markup=main_menu(lang)
    )


# ══════════════════════════════════════════
#  СТАРТ
# ══════════════════════════════════════════

def start(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    db.log_event("start", uid)
    saved = db.get_user_lang(uid)
    if saved:
        context.user_data["lang"] = saved
        lang = saved
        send_logo(
            context.bot, update.effective_chat.id,
            caption=t(lang, "welcome"),
            reply_markup=main_menu(lang)
        )
    else:
        send_logo(
            context.bot, update.effective_chat.id,
            caption=t("ru", "choose_lang"),
            reply_markup=lang_kb()
        )


# ══════════════════════════════════════════
#  ИНФОРМАЦИОННЫЕ РАЗДЕЛЫ
# ══════════════════════════════════════════

def about(update: Update, context: CallbackContext):
    lang = get_lang(context, update.effective_user.id)
    send_logo(context.bot, update.effective_chat.id, caption=t(lang, "about"))


def how_to_order(update: Update, context: CallbackContext):
    lang = get_lang(context, update.effective_user.id)
    update.message.reply_text(t(lang, "how_to_text"), parse_mode="Markdown")


def delivery_info(update: Update, context: CallbackContext):
    lang = get_lang(context, update.effective_user.id)
    update.message.reply_text(t(lang, "delivery_text"), parse_mode="Markdown")


def contact_manager(update: Update, context: CallbackContext):
    lang = get_lang(context, update.effective_user.id)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "💬 Написать в Telegram",
            url=f"https://t.me/{config.MANAGER_USERNAME.lstrip('@')}"
        )
    ]])
    texts = {
        "ru": (
            f"💬 *Связь с менеджером*\n\n"
            f"📞 Телефон: `{config.MANAGER_PHONE}`\n"
            f"💬 Telegram: {config.MANAGER_USERNAME}\n\n"
            f"Нажмите кнопку ниже или позвоните/напишите напрямую 👇"
        ),
        "az": (
            f"💬 *Menecer ilə əlaqə*\n\n"
            f"📞 Telefon: `{config.MANAGER_PHONE}`\n"
            f"💬 Telegram: {config.MANAGER_USERNAME}\n\n"
            f"Aşağıdakı düyməyə basın və ya birbaşa zəng edin/yazın 👇"
        ),
        "en": (
            f"💬 *Contact Manager*\n\n"
            f"📞 Phone: `{config.MANAGER_PHONE}`\n"
            f"💬 Telegram: {config.MANAGER_USERNAME}\n\n"
            f"Tap the button below or call/write directly 👇"
        ),
    }
    update.message.reply_text(
        texts.get(lang, texts["ru"]),
        parse_mode="Markdown",
        reply_markup=kb
    )


# ══════════════════════════════════════════
#  КАТАЛОГ → КАТЕГОРИИ → ТОВАРЫ
# ══════════════════════════════════════════

def categories_kb(lang: str):
    cats = db.get_categories()
    if not cats:
        return None
    rows, row = [], []
    for cat in cats:
        label = f"{cat[1]} {db.cat_name(cat, lang)}"
        row.append(InlineKeyboardButton(label, callback_data=f"cat_{cat[0]}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def show_catalog(update: Update, context: CallbackContext):
    lang = get_lang(context, update.effective_user.id)
    db.log_event("catalog", update.effective_user.id)
    kb = categories_kb(lang)
    if not kb:
        update.message.reply_text(t(lang, "no_categories"))
        return
    update.message.reply_text(t(lang, "choose_cat"), reply_markup=kb)


def show_category_products(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    lang = get_lang(context, query.from_user.id)
    cat_id = int(query.data.split("_")[1])
    db.log_event("cat_view", query.from_user.id, cat_id)

    products = db.get_products_by_category(cat_id)
    query.edit_message_text(t(lang, "choose_cat"))

    if not products:
        query.message.reply_text(t(lang, "no_products"))
        return

    for p in products:
        send_product_card(query.bot, query.message.chat_id, p, lang)


def back_to_cats(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    lang = get_lang(context, query.from_user.id)
    kb = categories_kb(lang)
    if kb:
        query.edit_message_text(t(lang, "choose_cat"), reply_markup=kb)
    else:
        query.edit_message_text(t(lang, "no_categories"))


# ══════════════════════════════════════════
#  ОФОРМЛЕНИЕ ЗАКАЗА
# ══════════════════════════════════════════

def order_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    lang = get_lang(context, query.from_user.id)
    pid = int(query.data.split("_")[1])
    product = db.get_product(pid)
    if not product:
        query.message.reply_text(t(lang, "product_gone"))
        return ConversationHandler.END

    context.user_data.update({
        "op_id":    pid,
        "op_name":  product[1],
        "op_price": product[3],
    })
    query.message.reply_text(
        f"📦 *{product[1]}*\n\n{t(lang, 'ask_size')}",
        parse_mode="Markdown"
    )
    return ORDER_SIZE


def order_size(update: Update, context: CallbackContext):
    context.user_data["o_size"] = update.message.text.strip()
    lang = get_lang(context, update.effective_user.id)
    update.message.reply_text(t(lang, "ask_qty"))
    return ORDER_QTY


def order_qty(update: Update, context: CallbackContext):
    lang = get_lang(context, update.effective_user.id)
    try:
        qty = int(update.message.text.strip())
        assert qty >= 1
    except (ValueError, AssertionError):
        update.message.reply_text(t(lang, "invalid_qty"))
        return ORDER_QTY
    context.user_data["o_qty"] = qty
    update.message.reply_text(t(lang, "ask_name"), parse_mode="Markdown")
    return ORDER_NAME


def order_name(update: Update, context: CallbackContext):
    context.user_data["o_name"] = update.message.text.strip()
    lang = get_lang(context, update.effective_user.id)
    update.message.reply_text(t(lang, "ask_phone"), parse_mode="Markdown")
    return ORDER_PHONE


def order_phone(update: Update, context: CallbackContext):
    context.user_data["o_phone"] = update.message.text.strip()
    lang = get_lang(context, update.effective_user.id)
    update.message.reply_text(t(lang, "ask_address"), parse_mode="Markdown")
    return ORDER_ADDRESS


def order_address(update: Update, context: CallbackContext):
    lang = get_lang(context, update.effective_user.id)
    context.user_data["o_addr"] = update.message.text.strip()
    ud = context.user_data
    total = ud["op_price"] * ud["o_qty"]
    text = t(lang, "order_summary").format(
        product=ud["op_name"], size=ud["o_size"], qty=ud["o_qty"],
        total=f"{total:.0f}", currency=config.CURRENCY,
        name=ud["o_name"], phone=ud["o_phone"], address=ud["o_addr"],
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "confirm_btn"), callback_data="confirm_order"),
        InlineKeyboardButton(t(lang, "cancel_btn"),  callback_data="cancel_order"),
    ]])
    update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    return ORDER_CONFIRM


def order_confirm(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    lang = get_lang(context, query.from_user.id)

    if query.data == "cancel_order":
        query.edit_message_text(t(lang, "order_cancelled"))
        context.user_data.clear()
        return ConversationHandler.END

    ud = context.user_data
    user = query.from_user
    order_id = db.create_order(
        user_id=user.id, username=user.username or "",
        full_name=ud["o_name"], product_id=ud["op_id"],
        size=ud["o_size"], quantity=ud["o_qty"],
        address=ud["o_addr"], phone=ud["o_phone"], lang=lang,
    )
    db.log_event("order", user.id, order_id)

    # Сообщение клиенту
    query.edit_message_text(t(lang, "order_done").format(id=order_id), parse_mode="Markdown")

    # Уведомление админу — подробное
    total = ud["op_price"] * ud["o_qty"]
    try:
        context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=(
                f"🔔 *НОВЫЙ ЗАКАЗ №{order_id}*\n"
                f"{'═' * 28}\n"
                f"🛍 *Товар:* {ud['op_name']}\n"
                f"📐 *Размер:* {ud['o_size']}\n"
                f"🔢 *Кол-во:* {ud['o_qty']} шт.\n"
                f"💰 *Сумма:* {total:.0f} {config.CURRENCY}\n"
                f"{'─' * 28}\n"
                f"👤 *Покупатель:* {ud['o_name']}\n"
                f"📞 *Телефон:* {ud['o_phone']}\n"
                f"🏠 *Адрес:* {ud['o_addr']}\n"
                f"🌐 *Telegram:* @{user.username or '—'} (ID: {user.id})\n"
                f"🗣 *Язык:* {lang.upper()}\n"
                f"{'─' * 28}\n"
                f"Управление: /setstatus {order_id} <статус>"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить админа: {e}")

    context.user_data.clear()
    return ConversationHandler.END


def order_cancel(update: Update, context: CallbackContext):
    lang = get_lang(context, update.effective_user.id)
    update.message.reply_text(t(lang, "order_cancelled"), reply_markup=main_menu(lang))
    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════
#  МОИ ЗАКАЗЫ
# ══════════════════════════════════════════

def my_orders(update: Update, context: CallbackContext):
    lang = get_lang(context, update.effective_user.id)
    conn = db.get_conn()
    rows = conn.execute("""
        SELECT o.id, p.name, o.size, o.quantity, o.status, o.created_at
        FROM orders o JOIN products p ON p.id = o.product_id
        WHERE o.user_id=? ORDER BY o.id DESC LIMIT 10
    """, (update.effective_user.id,)).fetchall()
    conn.close()

    if not rows:
        update.message.reply_text(t(lang, "no_orders"))
        return

    text = t(lang, "my_orders_hdr")
    st = STATUS_TEXT.get(lang, STATUS_TEXT["ru"])
    for oid, pname, size, qty, status, created in rows:
        emoji = STATUS_EMOJI.get(status, "❓")
        stext = st.get(status, status)
        text += f"*#{oid}* — {pname} ({size} × {qty})\n{emoji} {stext}\n📅 {created[:10]}\n\n"
    update.message.reply_text(text, parse_mode="Markdown")


# ══════════════════════════════════════════
#  РОУТЕР КНОПОК МЕНЮ
# ══════════════════════════════════════════

ALL_BTNS = {
    key: {t(lang, key) for lang in ("ru", "az", "en")}
    for key in ("catalog_btn", "orders_btn", "how_to_btn", "delivery_btn",
                "manager_btn", "about_btn", "language_btn")
}


def menu_router(update: Update, context: CallbackContext):
    text = update.message.text
    if text in ALL_BTNS["catalog_btn"]:
        show_catalog(update, context)
    elif text in ALL_BTNS["orders_btn"]:
        my_orders(update, context)
    elif text in ALL_BTNS["how_to_btn"]:
        how_to_order(update, context)
    elif text in ALL_BTNS["delivery_btn"]:
        delivery_info(update, context)
    elif text in ALL_BTNS["manager_btn"]:
        contact_manager(update, context)
    elif text in ALL_BTNS["about_btn"]:
        about(update, context)
    elif text in ALL_BTNS["language_btn"]:
        choose_language(update, context)
    elif text == "🏠 Главное меню":
        lang = get_lang(context, update.effective_user.id)
        update.message.reply_text(t(lang, "welcome"), reply_markup=main_menu(lang))


# ══════════════════════════════════════════
#  АДМИН: ПАНЕЛЬ + СТАТИСТИКА
# ══════════════════════════════════════════

ADMIN_MENU = ReplyKeyboardMarkup(
    [["📦 Все заказы",    "➕ Добавить товар"],
     ["🗑 Удалить товар", "📊 Статистика"],
     ["🏠 Главное меню"]],
    resize_keyboard=True
)


def admin_panel(update: Update, context: CallbackContext):
    if not is_admin(update):
        update.message.reply_text("🚫 Нет доступа.")
        return
    update.message.reply_text(
        "👑 *Панель администратора*\n\n"
        "Нажмите *🛍 Каталог* в главном меню, чтобы просмотреть магазин как покупатель.",
        parse_mode="Markdown", reply_markup=ADMIN_MENU
    )


def admin_stats(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    s = db.get_stats()
    text = (
        "📊 *Статистика магазина*\n"
        f"{'═' * 28}\n\n"
        f"👥 *Пользователей:*\n"
        f"   Всего: *{s['total_users']}*\n"
        f"   Сегодня: *{s['users_today']}* | За 7 дней: *{s['users_week']}*\n\n"
        f"🛒 *Заказов:*\n"
        f"   Всего: *{s['total_orders']}*\n"
        f"   Сегодня: *{s['orders_today']}* | За 7 дней: *{s['orders_week']}*\n\n"
    )
    if s["top_cats"]:
        text += "🔥 *Топ категорий:*\n"
        for i, (emoji, name_ru, cnt) in enumerate(s["top_cats"], 1):
            text += f"   {i}. {emoji} {name_ru} — {cnt} просм.\n"
        text += "\n"
    if s["top_products"]:
        text += "👀 *Топ товаров:*\n"
        for i, (name, cnt) in enumerate(s["top_products"], 1):
            text += f"   {i}. {name} — {cnt} просм.\n"
    update.message.reply_text(text, parse_mode="Markdown")


def admin_orders(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    orders = db.get_orders()
    if not orders:
        update.message.reply_text("Заказов пока нет.")
        return
    text = "📦 *Все заказы:*\n\n"
    st = STATUS_TEXT["ru"]
    for o in orders[:20]:
        oid, fname, uname, pname, size, qty, addr, phone, status, created = o
        emoji = STATUS_EMOJI.get(status, "❓")
        stext = st.get(status, status)
        text += (
            f"*#{oid}* {emoji} {stext}\n"
            f"👤 {fname} (@{uname}) | 📞 {phone}\n"
            f"🛍 {pname} — {size} × {qty}\n"
            f"🏠 {addr} | 📅 {created[:10]}\n"
            f"{'─' * 28}\n"
        )
    update.message.reply_text(text, parse_mode="Markdown")


def admin_status_hint(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    statuses_list = "\n".join([f"`{s}`" for s in ALL_STATUSES])
    update.message.reply_text(
        f"Команда: `/setstatus <id_заказа> <статус>`\n\n"
        f"*Доступные статусы:*\n{statuses_list}",
        parse_mode="Markdown"
    )


def set_status(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    args = context.args
    if len(args) != 2 or args[1] not in ALL_STATUSES:
        statuses_str = " | ".join(ALL_STATUSES)
        update.message.reply_text(
            f"Формат: /setstatus <id> <статус>\n\nСтатусы: {statuses_str}"
        )
        return
    try:
        order_id = int(args[0])
    except ValueError:
        update.message.reply_text("Введите корректный ID заказа.")
        return
    order = db.get_order(order_id)
    if not order:
        update.message.reply_text(f"Заказ #{order_id} не найден.")
        return

    status = args[1]
    db.update_order_status(order_id, status)
    emoji = STATUS_EMOJI.get(status, "")
    stext_ru = STATUS_TEXT["ru"].get(status, status)
    update.message.reply_text(f"✅ Заказ #{order_id} → {emoji} {stext_ru}")

    # Уведомляем клиента на его языке
    client_lang = order[11] if len(order) > 11 and order[11] else "ru"
    client_stext = STATUS_TEXT.get(client_lang, STATUS_TEXT["ru"]).get(status, status)
    try:
        context.bot.send_message(
            chat_id=order[1],
            text=t(client_lang, "status_update").format(
                emoji=emoji,
                id=order_id,
                status=f"*{client_stext}*",
                product=order[4],
                manager=config.MANAGER_USERNAME,
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить клиента: {e}")


def admin_del_hint(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    products = db.get_all_products()
    if not products:
        update.message.reply_text("Товаров нет.")
        return
    text = "Для удаления: `/delproduct <id>`\n\n*Товары:*\n"
    for p in products:
        pid, name, _, price, _, _, _, cat_emoji, cat_name_ru = p
        text += f"  #{pid} {cat_emoji or ''}  {name} — {price:.0f} ₽\n"
    update.message.reply_text(text, parse_mode="Markdown")


def del_product(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    if not context.args:
        update.message.reply_text("Формат: /delproduct <id>")
        return
    try:
        db.delete_product(int(context.args[0]))
        update.message.reply_text(f"✅ Товар #{context.args[0]} удалён.")
    except ValueError:
        update.message.reply_text("Введите корректный ID.")


# ══════════════════════════════════════════
#  ДОБАВЛЕНИЕ ТОВАРА (диалог)
# ══════════════════════════════════════════

def add_product_start(update: Update, context: CallbackContext):
    if not is_admin(update):
        return ConversationHandler.END
    cats = db.get_categories()
    if not cats:
        update.message.reply_text("Нет категорий.")
        return ConversationHandler.END

    rows, row = [], []
    for cat in cats:
        label = f"{cat[1]} {cat[2]}"
        row.append(InlineKeyboardButton(label, callback_data=f"addcat_{cat[0]}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="addcat_cancel")])

    update.message.reply_text(
        "📂 Выберите *категорию* товара:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return ADD_CATEGORY


def add_product_category(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if query.data == "addcat_cancel":
        query.edit_message_text("❌ Добавление отменено.")
        return ConversationHandler.END
    context.user_data["np_cat"] = int(query.data.split("_")[1])
    query.edit_message_text("Введите *название товара*:", parse_mode="Markdown")
    return ADD_NAME


def add_product_name(update: Update, context: CallbackContext):
    context.user_data["np_name"] = update.message.text.strip()
    update.message.reply_text("Введите *описание* товара:", parse_mode="Markdown")
    return ADD_DESC


def add_product_desc(update: Update, context: CallbackContext):
    context.user_data["np_desc"] = update.message.text.strip()
    update.message.reply_text("Введите *цену* в рублях (только число):", parse_mode="Markdown")
    return ADD_PRICE


def add_product_price(update: Update, context: CallbackContext):
    try:
        price = float(update.message.text.strip().replace(",", "."))
        assert price > 0
    except (ValueError, AssertionError):
        update.message.reply_text("⚠️ Введите корректную цену (число > 0):")
        return ADD_PRICE
    context.user_data["np_price"] = price
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📷 Фото",        callback_data="mediatype_photo"),
        InlineKeyboardButton("📹 Видео",        callback_data="mediatype_video"),
        InlineKeyboardButton("📝 Только текст", callback_data="mediatype_text"),
    ]])
    update.message.reply_text(
        "Выберите *тип медиа* для карточки товара:",
        parse_mode="Markdown", reply_markup=kb
    )
    return ADD_MEDIA_TYPE


def add_product_media_type(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    media_type = query.data.split("_")[1]
    context.user_data["np_media_type"] = media_type

    if media_type == "photo":
        query.edit_message_text("📷 Отправьте *фото* товара (или /skip):", parse_mode="Markdown")
        return ADD_MEDIA
    elif media_type == "video":
        query.edit_message_text("📹 Отправьте *видео* товара (или /skip):", parse_mode="Markdown")
        return ADD_MEDIA
    else:
        _save_product(context, None, None, "none")
        query.edit_message_text(
            f"✅ Товар *{context.user_data.get('np_name', '')}* добавлен (текстовая карточка)!",
            parse_mode="Markdown"
        )
        context.user_data.clear()
        return ConversationHandler.END


def add_product_media(update: Update, context: CallbackContext):
    ud = context.user_data
    photo_id, video_id, media_type = None, None, "none"

    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        media_type = "photo"
    elif update.message.video:
        video_id = update.message.video.file_id
        media_type = "video"
    else:
        update.message.reply_text("⚠️ Отправьте фото или видео, либо /skip:")
        return ADD_MEDIA

    _save_product(context, photo_id, video_id, media_type)
    update.message.reply_text(
        f"✅ Товар *{ud.get('np_name', '')}* добавлен в каталог!",
        parse_mode="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END


def add_product_skip_media(update: Update, context: CallbackContext):
    ud = context.user_data
    _save_product(context, None, None, "none")
    update.message.reply_text(
        f"✅ Товар *{ud.get('np_name', '')}* добавлен (без медиа)!",
        parse_mode="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END


def _save_product(context: CallbackContext, photo_id, video_id, media_type):
    ud = context.user_data
    db.add_product(
        name=ud["np_name"], desc=ud["np_desc"], price=ud["np_price"],
        category_id=ud["np_cat"], media_type=media_type,
        photo_id=photo_id, video_id=video_id,
    )


def cancel_add(update: Update, context: CallbackContext):
    update.message.reply_text("❌ Добавление товара отменено.", reply_markup=ADMIN_MENU)
    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════

def main():
    db.init_db()
    updater = Updater(config.BOT_TOKEN)
    dp = updater.dispatcher

    # ── Диалог: оформление заказа ──
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_start, pattern=r"^order_\d+$")],
        states={
            ORDER_SIZE:    [MessageHandler(Filters.text & ~Filters.command, order_size)],
            ORDER_QTY:     [MessageHandler(Filters.text & ~Filters.command, order_qty)],
            ORDER_NAME:    [MessageHandler(Filters.text & ~Filters.command, order_name)],
            ORDER_PHONE:   [MessageHandler(Filters.text & ~Filters.command, order_phone)],
            ORDER_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, order_address)],
            ORDER_CONFIRM: [CallbackQueryHandler(order_confirm,
                                                  pattern=r"^(confirm|cancel)_order$")],
        },
        fallbacks=[CommandHandler("cancel", order_cancel)],
    )

    # ── Диалог: добавление товара ──
    add_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex("^➕ Добавить товар$"), add_product_start)],
        states={
            ADD_CATEGORY:   [CallbackQueryHandler(add_product_category,  pattern=r"^addcat_")],
            ADD_NAME:       [MessageHandler(Filters.text & ~Filters.command, add_product_name)],
            ADD_DESC:       [MessageHandler(Filters.text & ~Filters.command, add_product_desc)],
            ADD_PRICE:      [MessageHandler(Filters.text & ~Filters.command, add_product_price)],
            ADD_MEDIA_TYPE: [CallbackQueryHandler(add_product_media_type, pattern=r"^mediatype_")],
            ADD_MEDIA: [
                MessageHandler(Filters.photo | Filters.video, add_product_media),
                CommandHandler("skip", add_product_skip_media),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
    )

    # ── Команды ──
    dp.add_handler(CommandHandler("start",      start))
    dp.add_handler(CommandHandler("admin",      admin_panel))
    dp.add_handler(CommandHandler("setstatus",  set_status))
    dp.add_handler(CommandHandler("delproduct", del_product))
    dp.add_handler(CommandHandler("stats",      admin_stats))

    # ── Callback-кнопки ──
    dp.add_handler(CallbackQueryHandler(set_language,           pattern=r"^lang_(ru|az|en)$"))
    dp.add_handler(CallbackQueryHandler(show_category_products, pattern=r"^cat_\d+$"))
    dp.add_handler(CallbackQueryHandler(back_to_cats,           pattern=r"^back_to_cats$"))

    # ── Диалоги ──
    dp.add_handler(order_conv)
    dp.add_handler(add_conv)

    # ── Кнопки админ-панели ──
    dp.add_handler(MessageHandler(Filters.regex("^📦 Все заказы$"),    admin_orders))
    dp.add_handler(MessageHandler(Filters.regex("^📊 Статистика$"),     admin_stats))
    dp.add_handler(MessageHandler(Filters.regex("^🗑 Удалить товар$"),  admin_del_hint))

    # ── Всё остальное → роутер главного меню ──
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, menu_router))

    logger.info("🤖 Бот запущен!")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
