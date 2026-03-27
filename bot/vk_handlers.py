import logging
from typing import Optional
from collections import defaultdict
import re
from pymongo import MongoClient, UpdateOne
from bot.api.timetable import TimetableAPI
from bot.utils import validate_email
from bot.localizer import localize
from bot.vk_menu import get_main_menu, get_login_menu
from bot.constants import get_current_date, get_tomorrow_date

logger = logging.getLogger(__name__)

MAIN_MENU = get_main_menu()
LOGIN_MENU = get_login_menu()


class VKHandlers:
    def __init__(self, bot):
        self.bot = bot
        try:
            config = bot.config
            self.client = MongoClient(config.mongo_uri)
            self.client.admin.command("ping")
            self.collection = self.client[config.mongo_db][config.mongo_collection]
        except ImportError:
            raise ImportError("pip install pymongo")
        except Exception as e:
            raise ConnectionError(f"Не удалось подключиться к MongoDB: {e}")

        self.api = TimetableAPI()

    @staticmethod
    def _get_user_id(peer_id: int) -> str:
        return str(peer_id)

    def _get(self, key: str) -> Optional[str]:
        doc = self.collection.find_one({"_id": key})
        return doc.get("value") if doc else None

    def _set(self, key: str, value: str) -> None:
        self.collection.update_one(
            {"_id": key},
            {"$set": {"value": value}},
            upsert=True,
        )

    def _set_many(self, data: dict[str, str]) -> None:
        operations = [
            UpdateOne({"_id": key}, {"$set": {"value": value}}, upsert=True)
            for key, value in data.items()
        ]
        if operations:
            self.collection.bulk_write(operations)

    def _delete(self, key: str) -> None:
        self.collection.delete_one({"_id": key})

    def _delete_many(self, keys: list[str]) -> None:
        if keys:
            self.collection.delete_many({"_id": {"$in": keys}})

    async def start_handler(self, peer_id: int, context: dict):
        text = localize("StartHandler", {"BtnLogin": "🔑 Авторизация"})
        self.bot._send_message(peer_id, text, LOGIN_MENU)

    def _init_login_state(self, user_id: str, university: str = "T"):
        self._set_many({
            user_id: university,
            f"{user_id}:login_state": "waiting_login",
            f"{user_id}:login_university": university
        })

    async def login_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)

        login_state = self._get(f"{user_id}:login_state")
        if login_state in ["waiting_login", "waiting_password"]:
            logger.info(f"Пользователь {user_id}: сброс состояния авторизации")
            self._cleanup_login_state(user_id)

        logger.info(f"Пользователь {user_id}: запрос авторизации")
        self._init_login_state(user_id)
        text = localize("LoginHandler", {})
        self.bot._send_message(peer_id, text)
        logger.info(f"Пользователь {user_id}: ожидание ввода логина")

    async def logout_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)

        if not self._get(user_id):
            self.bot._send_message(peer_id, localize("LogoutNotAuthError", {}))
            return

        self._delete(user_id)
        self.bot._send_message(peer_id, localize("LogoutCompleteMessage", {}), LOGIN_MENU)

    async def help_handler(self, peer_id: int, context: dict):
        text = localize("HelpHandler", {
            "BtnToday": "📖 Сегодня",
            "BtnTomorrow": "📖 Завтра",
            "BtnWeek": "📖 Неделя"
        })
        self.bot._send_message(peer_id, text)

    async def today_handler(self, peer_id: int, context: dict):
        await self._send_timetable(peer_id, "today")

    async def tomorrow_handler(self, peer_id: int, context: dict):
        await self._send_timetable(peer_id, "tomorrow")

    async def week_handler(self, peer_id: int, context: dict):
        await self._send_timetable(peer_id, "week")

    def _cleanup_login_state(self, user_id: str):
        self._delete_many([
            f"{user_id}:login_state",
            f"{user_id}:login_username",
            f"{user_id}:login_university"
        ])

    async def text_message_handler(self, peer_id: int, context: dict):
        user_id = self._get_user_id(peer_id)
        text = context['text'].strip()

        login_state = self._get(f"{user_id}:login_state")

        logger.info(f"Пользователь {user_id}: состояние={login_state}, текст={text}")

        if login_state == "waiting_login":
            logger.info(f"Пользователь {user_id}: сохранение логина и ожидание пароля")
            self._set_many({
                f"{user_id}:login_username": text,
                f"{user_id}:login_state": "waiting_password"
            })
            self.bot._send_message(peer_id, localize("LoginEnterPassword", {}))

        elif login_state == "waiting_password":
            username = self._get(f"{user_id}:login_username")
            user_university = self._get(f"{user_id}:login_university")

            logger.info(f"Пользователь {user_id}: логин={username}, вуз={user_university}, пароль={bool(text)}")

            if not username or not user_university:
                logger.error(f"Пользователь {user_id}: нет логина или вуза")
                self.bot._send_message(peer_id, localize("TryLaterError", {}))
                return

            self._cleanup_login_state(user_id)

            try:
                logger.info(f"Пользователь {user_id}: попытка авторизации через API")
                token_info = self.api.auth_user(user_university, username, text)
                logger.info(f"Пользователь {user_id}: ответ API state={token_info.get('state')}")

                if token_info.get('state') == -1:
                    logger.warning(f"Пользователь {user_id}: неверные учётные данные")
                    self.bot._send_message(peer_id, localize("LoginWrongLoginOrPasswordError", {}))
                    return

                access_token = token_info['data']['accessToken']
                api_user_id = str(token_info['data']['data']['id'])
                logger.info(f"Пользователь {user_id}: токен получен, api_user_id={api_user_id}")

                if not validate_email(username):
                    logger.info(f"Пользователь {user_id}: получение teacher_id")
                    teacher_id = self.api.get_teacher_id(user_university, access_token, api_user_id)
                    logger.info(f"Пользователь {user_id}: teacher_id={teacher_id}")
                    storage_value = f"{user_university}{teacher_id}T"
                else:
                    logger.info(f"Пользователь {user_id}: получение group_id")
                    group_id = self.api.get_student_group_id(user_university, access_token, api_user_id)
                    logger.info(f"Пользователь {user_id}: group_id={group_id}")
                    storage_value = f"{user_university}{group_id}"

                logger.info(f"Пользователь {user_id}: сохранение storage_value={storage_value}")
                self._set(user_id, storage_value)

                self.bot._send_message(
                    peer_id,
                    localize("LoginCompleteMessage", {"BtnLogout": "🚪 Выход"}),
                    MAIN_MENU
                )

            except Exception as e:
                logger.error(f"Пользователь {user_id}: ошибка авторизации: {e}", exc_info=True)
                self.bot._send_message(peer_id, localize("TryLaterError", {}))

    async def _send_timetable(self, peer_id: int, period: str):
        user_id = self._get_user_id(peer_id)
        storage_value = self._get(user_id)

        if not storage_value:
            self.bot._send_message(peer_id, localize("TimetableLoginFirstError", {}))
            return

        try:
            timetable = self.api.get_timetable(storage_value)
            text, parse_mode = self._format_timetable(timetable, storage_value, period)

            if not text or not text.strip():
                self.bot._send_message(peer_id, localize("TimetableEmpty", {}))
            else:
                plain_text = self._html_to_plain(text)
                self.bot._send_message(peer_id, plain_text)
        except Exception as e:
            logger.error(f"Ошибка получения расписания: пользователь {user_id}, ошибка: {e}", exc_info=True)
            self.bot._send_message(peer_id, localize("TryLaterError", {}))

    def _html_to_plain(self, text: str) -> str:
        text = re.sub(r'<b>(.*?)</b>', r'\1', text)
        text = re.sub(r'<i>(.*?)</i>', r'\1', text)
        text = re.sub(r'<code>(.*?)</code>', r'\1', text)
        text = re.sub(r'<.*?>', '', text)
        return text

    def _format_timetable(self, timetable: dict, storage_value: str, period: str):
        if not timetable or 'data' not in timetable or 'rasp' not in timetable['data']:
            return "", None

        items = timetable['data']['rasp']
        is_teacher = storage_value.endswith('T')

        if period == "today":
            current_date = get_current_date()
            filtered_items = [item for item in items if item.get('дата', '').startswith(current_date)]
        elif period == "tomorrow":
            tomorrow_date = get_tomorrow_date()
            filtered_items = [item for item in items if item.get('дата', '').startswith(tomorrow_date)]
        else:
            filtered_items = items

        if not filtered_items:
            return "", None

        lines = []
        if period == "week":
            by_day = defaultdict(list)
            for item in filtered_items:
                day_num = item.get('деньНедели', 0)
                if 1 <= day_num <= 7:
                    by_day[day_num].append(item)

            for day_num in sorted(by_day.keys()):
                day_items = by_day[day_num]
                if day_items:
                    day_name = day_items[0].get('день_недели', '')
                    if day_name.startswith('📅 '):
                        day_name = day_name[2:]
                    day_name = re.sub(r'\s+\d+$', '', day_name).strip()
                    lines.append(f"\n{day_name}\n")
                    for idx, item in enumerate(day_items):
                        lines.append(self._format_item(item, is_teacher, idx + 1))
                        if idx < len(day_items) - 1:
                            lines.append("\n\n")
        else:
            period_titles = {"today": "Сегодня", "tomorrow": "Завтра"}
            if period in period_titles:
                lines.append(f"{period_titles[period]}")

            for idx, item in enumerate(filtered_items):
                lines.append(self._format_item(item, is_teacher, idx + 1))
                if idx < len(filtered_items) - 1:
                    lines.append("\n\n")

        return "\n".join(lines), "text"

    def _get_lesson_type_emoji(self, discipline: str) -> str:
        discipline_lower = discipline.lower()
        if discipline_lower.startswith('лек'):
            return "🟢"
        elif discipline_lower.startswith('лаб'):
            return "🔵"
        elif discipline_lower.startswith('пр'):
            return "🟠"
        return "⚪"

    def _format_item(self, item: dict, is_teacher: bool, number: int = 0) -> str:
        discipline = item.get('дисциплина', '')

        if is_teacher:
            teacher_part = f"{item.get('группа', '')}"
        else:
            teacher_part = f"{item.get('преподаватель', '')}"

        start = item.get('начало', '')
        end = item.get('конец', '')
        audience = item.get('аудитория', '')

        number_prefix = f"{number}. " if number > 0 else ""
        type_emoji = self._get_lesson_type_emoji(discipline)

        line1 = f"{number_prefix}{type_emoji} {discipline}"
        time_part = f"{start}–{end}" if start and end else (start or end)
        line2 = f"{teacher_part}  🕒 {time_part}"

        lines = [line1, line2]
        if audience:
            lines.append(f"📍 {audience}")

        return "\n".join(lines)
