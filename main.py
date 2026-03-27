import asyncio
import logging
from bot.vk_bot import VKBot
from bot.config import Config

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main():
    try:
        config = Config()
        bot = VKBot(config)
        await bot.start()
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}", exc_info=True)


if __name__ == '__main__':
    asyncio.run(main())
