import os

# =============================================
#  Конфигурация бота
#  Значения берутся из переменных окружения Railway.
#  Локально используются значения по умолчанию.
# =============================================

BOT_TOKEN        = os.environ.get("BOT_TOKEN",        "8649116588:AAGLhfCv9qgkp22HpI0Bsvr9G_I8WALzCEw")
ADMIN_ID         = int(os.environ.get("ADMIN_ID",     "7899234771"))
MANAGER_USERNAME = os.environ.get("MANAGER_USERNAME", "@povisq1e")
MANAGER_PHONE    = os.environ.get("MANAGER_PHONE",    "+994-051-571-77-71")

# База данных
DB_FILE = "shop.db"

# Валюта
CURRENCY = "₽"

# Логотип
LOGO_PATH    = "logo.jpg"
LOGO_FILE_ID = None          # заполняется автоматически при первом запуске
