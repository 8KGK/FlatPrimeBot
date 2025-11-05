"""
Модуль для роботи з налаштуваннями користувачів
"""

from database import get_connection

# Позиції водяного знака
WATERMARK_POSITIONS = {
    'center': 'По центру',
    'top_left': 'Зліва вгорі',
    'top_right': 'Справа вгорі',
    'bottom_left': 'Зліва внизу',
    'bottom_right': 'Справа внизу'
}


def get_watermark_position(telegram_user_id):
    """
    Отримує позицію водяного знака для користувача
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT watermark_position FROM user_settings
        WHERE telegram_user_id = %s
    """, (telegram_user_id,))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    # Якщо налаштування не знайдено - повертаємо центр за замовчуванням
    if result:
        return result[0]
    return 'center'


def set_watermark_position(telegram_user_id, position):
    """
    Встановлює позицію водяного знака для користувача
    """
    if position not in WATERMARK_POSITIONS:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_settings (telegram_user_id, watermark_position)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE
            watermark_position = %s,
            updated_at = CURRENT_TIMESTAMP
    """, (telegram_user_id, position, position))

    conn.commit()
    cursor.close()
    conn.close()

    return True


def get_position_name(position):
    return WATERMARK_POSITIONS.get(position, 'По центру')