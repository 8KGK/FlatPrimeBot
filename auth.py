"""
Модуль для управління авторизацією користувачів
Зберігає стан авторизації в базі даних MySQL
"""

from typing import Dict, Optional
from database import save_session, load_session, delete_session, load_all_sessions

# Словник для зберігання авторизованих користувачів (кеш)
# Формат: {telegram_user_id: {"user_id": db_user_id, "name": user_name}}
authorized_users: Dict[int, dict] = {}

# Словник для зберігання стану очікування паролю (тільки в пам'яті)
# Формат: {telegram_user_id: db_user_id}
pending_auth: Dict[int, int] = {}


def init_sessions():
    """
    Завантажує всі активні сесії з БД при запуску бота
    """
    global authorized_users
    authorized_users = load_all_sessions()
    print(f"✅ Завантажено {len(authorized_users)} активних сесій")


def is_authorized(telegram_user_id: int) -> bool:
    """
    Перевіряє чи авторизований користувач

    Args:
        telegram_user_id (int): Telegram ID користувача

    Returns:
        bool: True якщо авторизований
    """
    # Перевіряємо в кеші
    if telegram_user_id in authorized_users:
        return True

    # Якщо немає в кеші - перевіряємо в БД
    session = load_session(telegram_user_id)
    if session:
        user_id, user_name = session
        authorized_users[telegram_user_id] = {
            "user_id": user_id,
            "name": user_name
        }
        return True

    return False


def authorize_user(telegram_user_id: int, user_id: int, user_name: str):
    """
    Авторизує користувача (зберігає в БД та кеш)

    Args:
        telegram_user_id (int): Telegram ID користувача
        user_id (int): ID користувача в БД
        user_name (str): Ім'я користувача
    """
    # Зберігаємо в БД
    save_session(telegram_user_id, user_id, user_name)

    # Зберігаємо в кеші
    authorized_users[telegram_user_id] = {
        "user_id": user_id,
        "name": user_name
    }

    # Видаляємо з очікування паролю якщо був
    if telegram_user_id in pending_auth:
        del pending_auth[telegram_user_id]


def logout_user(telegram_user_id: int):
    """
    Виходить з аккаунту (видаляє з БД та кешу)

    Args:
        telegram_user_id (int): Telegram ID користувача
    """
    # Видаляємо з БД
    delete_session(telegram_user_id)

    # Видаляємо з кешу
    if telegram_user_id in authorized_users:
        del authorized_users[telegram_user_id]

    if telegram_user_id in pending_auth:
        del pending_auth[telegram_user_id]


def get_authorized_user(telegram_user_id: int) -> Optional[dict]:
    """
    Отримує дані авторизованого користувача

    Args:
        telegram_user_id (int): Telegram ID користувача

    Returns:
        Optional[dict]: Дані користувача або None
    """
    # Перевіряємо в кеші
    if telegram_user_id in authorized_users:
        return authorized_users[telegram_user_id]

    # Якщо немає в кеші - перевіряємо в БД
    session = load_session(telegram_user_id)
    if session:
        user_id, user_name = session
        authorized_users[telegram_user_id] = {
            "user_id": user_id,
            "name": user_name
        }
        return authorized_users[telegram_user_id]

    return None


def set_pending_auth(telegram_user_id: int, user_id: int):
    """
    Встановлює стан очікування паролю (тільки в пам'яті)

    Args:
        telegram_user_id (int): Telegram ID користувача
        user_id (int): ID користувача в БД
    """
    pending_auth[telegram_user_id] = user_id


def get_pending_auth(telegram_user_id: int) -> Optional[int]:
    """
    Отримує ID користувача що очікує введення паролю

    Args:
        telegram_user_id (int): Telegram ID користувача

    Returns:
        Optional[int]: ID користувача в БД або None
    """
    return pending_auth.get(telegram_user_id)


def clear_pending_auth(telegram_user_id: int):
    """
    Очищає стан очікування паролю

    Args:
        telegram_user_id (int): Telegram ID користувача
    """
    if telegram_user_id in pending_auth:
        del pending_auth[telegram_user_id]