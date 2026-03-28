import json


def get_main_menu() -> dict:
    """Get main menu keyboard for VK"""
    keyboard = {
        'one_time': False,
        'inline': False,
        'buttons': [
            [
                {
                    'action': {
                        'type': 'text',
                        'label': '📖 Сегодня',
                        'payload': json.dumps({'button': '📖 Сегодня'})
                    }
                },
                {
                    'action': {
                        'type': 'text',
                        'label': '📖 Завтра',
                        'payload': json.dumps({'button': '📖 Завтра'})
                    }
                }
            ],
            [
                {
                    'action': {
                        'type': 'text',
                        'label': '📖 Неделя',
                        'payload': json.dumps({'button': '📖 Неделя'})
                    }
                },
                {
                    'action': {
                        'type': 'text',
                        'label': 'ℹ Помощь',
                        'payload': json.dumps({'button': 'ℹ Помощь'})
                    }
                }
            ],
            [
                {
                    'action': {
                        'type': 'text',
                        'label': '🚪 Выход',
                        'payload': json.dumps({'button': '🚪 Выход'})
                    }
                }
            ]
        ]
    }
    return keyboard


def get_login_menu() -> dict:
    """Get login menu keyboard for VK"""
    keyboard = {
        'one_time': False,
        'inline': False,
        'buttons': [
            [
                {
                    'action': {
                        'type': 'text',
                        'label': '🔑 Авторизация',
                        'payload': json.dumps({'button': '🔑 Авторизация'})
                    }
                }
            ]
        ]
    }
    return keyboard
