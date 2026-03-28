from datetime import datetime, timedelta
import pytz

TPI_DGTY_API_URL = "https://edu-tpi.donstu.ru/api"
DGTY_API_URL = "https://edu.donstu.ru/api"

AUTH_PATH = "/tokenauth"
GET_STUDENT_PATH = "/UserInfo/Student"
GET_TEACHER_PATH = "/UserInfo/user"

MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_current_date() -> str:
    return datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')


def get_tomorrow_date() -> str:
    tomorrow = datetime.now(MOSCOW_TZ) + timedelta(days=1)
    return tomorrow.strftime('%Y-%m-%d')
