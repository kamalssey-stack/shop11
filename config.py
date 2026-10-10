import os

# =============================================
#  Конфигурация бота
#  Значения берутся из переменных окружения Railway.
#  Локально используются значения по умолчанию.
# =============================================

raw_token = os.environ.get("BOT_TOKEN", "8649116588:AAGLhfCv9qgkp22HpI0Bsvr9G_I8WALzCEw")
BOT_TOKEN = raw_token.strip().strip('"').strip("'")

raw_admin = os.environ.get("ADMIN_ID", "7899234771")
try:
    ADMIN_ID = int(str(raw_admin).strip().strip('"').strip("'"))
except ValueError:
    ADMIN_ID = 7899234771

MANAGER_USERNAME = os.environ.get("MANAGER_USERNAME", "@povisq1e").strip().strip('"').strip("'")
MANAGER_PHONE    = os.environ.get("MANAGER_PHONE",    "+994-051-571-77-71").strip().strip('"').strip("'")

# База данных
DB_FILE = "shop.db"

# Валюта
CURRENCY = "₽"

# Логотип
LOGO_PATH    = "logo.jpg"
LOGO_FILE_ID = None          # заполняется автоматически при первом запуске
