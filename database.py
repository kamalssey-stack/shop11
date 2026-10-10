import sqlite3
from config import DB_FILE

DEFAULT_CATEGORIES = [
    ("🧥", "Куртки",            "Gödəklər",          "Jackets"),
    ("👕", "Майки / Футболки",   "Futbolkalar",        "T-Shirts"),
    ("👖", "Штаны / Джинсы",    "Şalvarlar",          "Pants / Jeans"),
    ("🧸", "Толстовки / Худи",  "Hoodie / Sviterlər", "Hoodies / Sweatshirts"),
    ("👗", "Платья / Юбки",     "Paltarlar",          "Dresses / Skirts"),
    ("👟", "Кроссовки / Обувь", "Ayaqqabılar",        "Sneakers / Shoes"),
    ("👜", "Сумки",             "Çantalar",           "Bags"),
    ("🧢", "Аксессуары",        "Aksesuarlar",        "Accessories"),
    ("🧣", "Нижнее бельё",      "Alt paltarlar",      "Underwear"),
    ("🕶️","Очки / Часы",       "Eynək / Saatlar",    "Glasses / Watches"),
]


def get_conn():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            emoji   TEXT    DEFAULT '📦',
            name_ru TEXT    NOT NULL,
            name_az TEXT    NOT NULL,
            name_en TEXT    NOT NULL,
            active  INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            desc        TEXT,
            price       REAL    NOT NULL,
            photo_id    TEXT,
            video_id    TEXT,
            media_type  TEXT    DEFAULT 'none',
            category_id INTEGER,
            active      INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER  PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER  NOT NULL,
            username   TEXT,
            full_name  TEXT,
            product_id INTEGER  NOT NULL,
            size       TEXT,
            quantity   INTEGER  DEFAULT 1,
            address    TEXT,
            phone      TEXT,
            comment    TEXT,
            status     TEXT     DEFAULT 'new',
            lang       TEXT     DEFAULT 'ru',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            lang    TEXT    DEFAULT 'ru'
        )
    """)

    # Аналитика (event_type + user_id + extra_id)
    c.execute("""
        CREATE TABLE IF NOT EXISTS analytics (
            id         INTEGER  PRIMARY KEY AUTOINCREMENT,
            event_type TEXT     NOT NULL,
            user_id    INTEGER  NOT NULL,
            extra_id   INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Безопасные миграции
    for col, typedef in [
        ("video_id",    "TEXT"),
        ("media_type",  "TEXT DEFAULT 'none'"),
        ("category_id", "INTEGER"),
    ]:
        try:
            c.execute(f"ALTER TABLE products ADD COLUMN {col} {typedef}")
        except Exception:
            pass

    try:
        c.execute("ALTER TABLE orders ADD COLUMN lang TEXT DEFAULT 'ru'")
    except Exception:
        pass

    # Дефолтные категории при первом запуске
    if not c.execute("SELECT COUNT(*) FROM categories WHERE active=1").fetchone()[0]:
        for emoji, ru, az, en in DEFAULT_CATEGORIES:
            c.execute(
                "INSERT INTO categories (emoji, name_ru, name_az, name_en) VALUES (?,?,?,?)",
                (emoji, ru, az, en)
            )

    conn.commit()
    conn.close()


# ─────────── АНАЛИТИКА ───────────

def log_event(event_type: str, user_id: int, extra_id: int = None):
    """Логируем событие: start / catalog / cat_view / product_view / order"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO analytics (event_type, user_id, extra_id) VALUES (?,?,?)",
        (event_type, user_id, extra_id)
    )
    conn.commit()
    conn.close()


def get_stats() -> dict:
    conn = get_conn()

    def one(sql, *args):
        return conn.execute(sql, args).fetchone()[0]

    def many(sql, *args):
        return conn.execute(sql, args).fetchall()

    stats = {
        "total_users":  one("SELECT COUNT(DISTINCT user_id) FROM analytics WHERE event_type='start'"),
        "users_today":  one("SELECT COUNT(DISTINCT user_id) FROM analytics WHERE event_type='start' AND date(created_at)=date('now')"),
        "users_week":   one("SELECT COUNT(DISTINCT user_id) FROM analytics WHERE event_type='start' AND created_at>=datetime('now','-7 days')"),
        "total_orders": one("SELECT COUNT(*) FROM orders"),
        "orders_today": one("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')"),
        "orders_week":  one("SELECT COUNT(*) FROM orders WHERE created_at>=datetime('now','-7 days')"),
        # Топ категорий
        "top_cats":     many("""
            SELECT c.emoji, c.name_ru, COUNT(a.id) as cnt
            FROM analytics a
            JOIN categories c ON c.id = a.extra_id
            WHERE a.event_type='cat_view'
            GROUP BY a.extra_id ORDER BY cnt DESC LIMIT 5
        """),
        # Топ товаров
        "top_products": many("""
            SELECT p.name, COUNT(a.id) as cnt
            FROM analytics a
            JOIN products p ON p.id = a.extra_id
            WHERE a.event_type='product_view'
            GROUP BY a.extra_id ORDER BY cnt DESC LIMIT 5
        """),
    }
    conn.close()
    return stats


# ─────────── КАТЕГОРИИ ───────────

def get_categories():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, emoji, name_ru, name_az, name_en FROM categories WHERE active=1"
    ).fetchall()
    conn.close()
    return rows


def cat_name(cat_row, lang: str) -> str:
    if lang == "az":
        return cat_row[3]
    if lang == "en":
        return cat_row[4]
    return cat_row[2]


def add_category(emoji: str, name_ru: str, name_az: str, name_en: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO categories (emoji, name_ru, name_az, name_en) VALUES (?,?,?,?)",
        (emoji, name_ru, name_az, name_en)
    )
    conn.commit()
    conn.close()


# ─────────── ТОВАРЫ ───────────

def get_products_by_category(category_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, desc, price, photo_id, video_id, media_type "
        "FROM products WHERE active=1 AND category_id=?",
        (category_id,)
    ).fetchall()
    conn.close()
    return rows


def get_all_products():
    conn = get_conn()
    rows = conn.execute(
        "SELECT p.id, p.name, p.desc, p.price, p.photo_id, p.video_id, p.media_type, "
        "       c.emoji, c.name_ru "
        "FROM products p LEFT JOIN categories c ON c.id = p.category_id "
        "WHERE p.active=1 ORDER BY p.id DESC"
    ).fetchall()
    conn.close()
    return rows


def get_product(product_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, name, desc, price, photo_id, video_id, media_type, category_id "
        "FROM products WHERE id=?",
        (product_id,)
    ).fetchone()
    conn.close()
    return row


def add_product(name, desc, price, category_id,
                media_type="none", photo_id=None, video_id=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO products (name, desc, price, category_id, media_type, photo_id, video_id) "
        "VALUES (?,?,?,?,?,?,?)",
        (name, desc, price, category_id, media_type, photo_id, video_id)
    )
    conn.commit()
    conn.close()


def delete_product(product_id: int):
    conn = get_conn()
    conn.execute("UPDATE products SET active=0 WHERE id=?", (product_id,))
    conn.commit()
    conn.close()


# ─────────── ЗАКАЗЫ ───────────

def create_order(user_id, username, full_name, product_id,
                 size, quantity, address, phone, lang="ru", comment=""):
    conn = get_conn()
    c = conn.execute(
        "INSERT INTO orders "
        "(user_id, username, full_name, product_id, size, quantity, address, phone, lang, comment) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (user_id, username, full_name, product_id,
         size, quantity, address, phone, lang, comment)
    )
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id


def get_orders():
    conn = get_conn()
    rows = conn.execute("""
        SELECT o.id, o.full_name, o.username, p.name, o.size, o.quantity,
               o.address, o.phone, o.status, o.created_at
        FROM orders o JOIN products p ON p.id = o.product_id
        ORDER BY o.id DESC
    """).fetchall()
    conn.close()
    return rows


def get_order(order_id: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT o.id, o.user_id, o.full_name, o.username, p.name, o.size,
               o.quantity, o.address, o.phone, o.status, o.comment, o.lang
        FROM orders o JOIN products p ON p.id = o.product_id
        WHERE o.id=?
    """, (order_id,)).fetchone()
    conn.close()
    return row


def update_order_status(order_id: int, status: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()


# ─────────── НАСТРОЙКИ ПОЛЬЗОВАТЕЛЯ ───────────

def get_user_lang(user_id: int) -> str:
    conn = get_conn()
    row = conn.execute(
        "SELECT lang FROM user_settings WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def set_user_lang(user_id: int, lang: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_settings (user_id, lang) VALUES (?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang",
        (user_id, lang)
    )
    conn.commit()
    conn.close()
