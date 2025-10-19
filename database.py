"""
Модуль для роботи з базою даних MySQL
Авторизація користувачів
"""

import mysql.connector
from typing import List, Optional, Tuple


def get_connection():
    """
    Створює з'єднання з базою даних MySQL
    """
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="Flat",
        autocommit=True
    )


def get_all_users() -> List[Tuple[int, str]]:
    """
    Отримує список всіх користувачів з бази даних
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT ID, Name FROM users ORDER BY Name")
        users = cursor.fetchall()

        cursor.close()
        conn.close()

        return users
    except Exception as e:
        print(f"Помилка отримання користувачів: {e}")
        return []


def verify_password(user_id: int, password: str) -> bool:
    """
    Перевіряє пароль користувача
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT Password FROM users WHERE ID = %s", (user_id,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            return result[0] == password
        return False
    except Exception as e:
        print(f"Помилка перевірки паролю: {e}")
        return False


def get_user_name(user_id: int) -> Optional[str]:
    """
    Отримує ім'я користувача за ID
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT Name FROM users WHERE ID = %s", (user_id,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        return result[0] if result else None
    except Exception as e:
        print(f"Помилка отримання імені: {e}")
        return None


def create_users_table():
    """
    Створює таблицю користувачів якщо вона не існує
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                ID INT AUTO_INCREMENT PRIMARY KEY,
                Name VARCHAR(255) NOT NULL,
                Password VARCHAR(255) NOT NULL
            )
        """)

        cursor.close()
        conn.close()

        print("✅ Таблиця користувачів готова")
    except Exception as e:
        print(f"❌ Помилка створення таблиці: {e}")


def create_sessions_table():
    """
    Створює таблицю сесій якщо вона не існує
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                telegram_user_id BIGINT PRIMARY KEY,
                user_id INT NOT NULL,
                user_name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.close()
        conn.close()

        print("✅ Таблиця сесій готова")
    except Exception as e:
        print(f"❌ Помилка створення таблиці сесій: {e}")


def save_session(telegram_user_id: int, user_id: int, user_name: str):
    """
    Зберігає сесію користувача в БД
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (telegram_user_id, user_id, user_name)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE user_id = %s, user_name = %s
        """, (telegram_user_id, user_id, user_name, user_id, user_name))

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Помилка збереження сесії: {e}")


def load_session(telegram_user_id: int) -> Optional[Tuple[int, str]]:
    """
    Завантажує сесію користувача з БД
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, user_name FROM sessions 
            WHERE telegram_user_id = %s
        """, (telegram_user_id,))

        result = cursor.fetchone()

        cursor.close()
        conn.close()

        return result if result else None
    except Exception as e:
        print(f"Помилка завантаження сесії: {e}")
        return None


def delete_session(telegram_user_id: int):
    """
    Видаляє сесію користувача з БД
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM sessions WHERE telegram_user_id = %s
        """, (telegram_user_id,))

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Помилка видалення сесії: {e}")


def load_all_sessions() -> dict:
    """
    Завантажує всі активні сесії з БД
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT telegram_user_id, user_id, user_name FROM sessions")
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        sessions = {}
        for telegram_user_id, user_id, user_name in results:
            sessions[telegram_user_id] = {
                "user_id": user_id,
                "name": user_name
            }

        return sessions
    except Exception as e:
        print(f"Помилка завантаження сесій: {e}")
        return {}
