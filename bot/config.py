import os


class Config:
    def __init__(self):
        self.vk_token: str = self._get_env('VK_TOKEN', '')
        self.vk_api_version: str = self._get_env('VK_API_VERSION', '5.131')
        self.mongo_uri: str = self._get_env('MONGO_URI', '')
        self.mongo_db: str = self._get_env('MONGO_DB', '')
        self.mongo_collection: str = self._get_env('MONGO_COLLECTION', '')

        if not self.vk_token:
            raise ValueError("VK_TOKEN обязателен для работы бота")

    @staticmethod
    def _get_env(key: str, default: str = '') -> str:
        return os.getenv(key, default)
