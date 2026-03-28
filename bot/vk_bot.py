import asyncio
import logging
import time
import json
from concurrent.futures import ThreadPoolExecutor
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from bot.config import Config
from bot.vk_handlers import VKHandlers
from bot.vk_menu import get_main_menu, get_login_menu
logger = logging.getLogger(__name__)

MAIN_MENU = get_main_menu()
LOGIN_MENU = get_login_menu()



class VKBot:
    bot_message_prefixes = [
                    "Пожалуйста, введите ваш логин:",
                    "Теперь введите ваш пароль:",
                    "Введен неправильный логин или пароль",
                    "Здравствуйте! Это неофициальный бот",
                    "Для взаимодействия с ботом используйте",
                    "Для начала вы должны авторизоваться",
                    "На этот день пар нет",
                    "Ошибка, пожалуйста попробуйте позже",
                    "В целях безопасности вы можете",
                    "Вы успешно вышли",
                    "Вы не авторизованы"
                ]
    def __init__(self, config: Config):
        self.config = config
        self.token = config.vk_token
        self.handlers = VKHandlers(self)
        self.running = False
        self.vk = None
        self.longpoll = None
        self.loop = None
        self._route: dict = {
            "Начать": self.handlers.start_handler,
            "📖 Сегодня": self.handlers.today_handler,
            "📖 Завтра": self.handlers.tomorrow_handler,
            "📖 Неделя": self.handlers.week_handler,
            'ℹ Помощь': self.handlers.help_handler,
            '🔑 Авторизация': self.handlers.login_handler,
            '🚪 Выход': self.handlers.logout_handler,
            "_": self.handlers.text_message_handler,
        }

    def _init_vk(self):
        try:
            self.vk = vk_api.VkApi(token=self.token)
            self.longpoll = VkLongPoll(self.vk)
        except Exception as e:
            logger.error(f"Ошибка подключения VK: {e}")
            raise

    def _send_message(self, peer_id: int, text: str, keyboard: dict = None) -> bool:
        try:
            params = {
                'peer_id': peer_id,
                'message': text,
                'random_id': int(time.time() * 1000000) & 0xFFFFFFFF
            }

            if keyboard:
                params['keyboard'] = json.dumps(keyboard)

            self.vk.method('messages.send', params)
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False

    def _process_event(self, event):
        try:
            if event.type == VkEventType.MESSAGE_NEW:
                if event.from_user:
                    peer_id = event.peer_id
                    text = event.text
                    from_id = event.user_id
                elif event.from_chat:
                    peer_id = event.peer_id
                    text = event.text
                    from_id = event.user_id
                else:
                    return

                if not text:
                    return
                if any(text.startswith(prefix) for prefix in self.bot_message_prefixes):
                    return

                context = {
                    'peer_id': peer_id,
                    'text': text,
                    'from_id': from_id
                }

                if self.loop:
                    logger.debug(f"Отправка в _route_message: {text!r}")
                    asyncio.run_coroutine_threadsafe(self._route_message(context), self.loop)
                else:
                    logger.error("Event loop не инициализирован")

        except Exception as e:
            logger.error(f"Ошибка обработки события: {e}", exc_info=True)

    async def _route_message(self, context: dict):
        text = context['text'].strip()
        peer_id = context['peer_id']

        logger.debug(f"_route_message: text={text!r}, peer_id={peer_id}")

        try:
            handler = self._route.get(text, self._route["_"])
            logger.debug(f"Выбран handler: {handler.__name__ if hasattr(handler, '__name__') else handler}")
            await handler(peer_id, context)
        except Exception as e:
            logger.error(f"Ошибка маршрутизации: {e}", exc_info=True)
            self._send_message(peer_id, "Произошла ошибка. Пожалуйста, попробуйте позже.")

    async def start(self):
        try:
            logger.info("Запуск бота...")
            self.running = True
            self.loop = asyncio.get_running_loop()

            self._init_vk()

            logger.info("Бот подключён")
            logger.info("LongPoll запущен")

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run_longpoll)
                await asyncio.wrap_future(future)

        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Остановка бота")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
        finally:
            await self.shutdown()

    def _run_longpoll(self):
        try:
            for event in self.longpoll.listen():
                if not self.running:
                    break
                self._process_event(event)
        except Exception as e:
            logger.error(f"Ошибка LongPoll: {e}", exc_info=True)

        self.longpoll = None