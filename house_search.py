"""
Модуль для пошуку інформації про будинки
"""

import re  # ДОДАНО: імпорт модуля re
from database import get_connection
from typing import Optional, List, Dict


def search_house_by_address(address: str, house_number: str) -> Optional[List[Dict]]:
    """
    Шукає будинок за точною адресою

    Args:
        address: Назва вулиці (наприклад: "Хрещатик")
        house_number: Номер будинку (наприклад: "15")

    Returns:
        Список знайдених будинків або None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Пошук за точною адресою та номером
        query = """
            SELECT * FROM houses 
            WHERE address LIKE %s AND house_number = %s
            ORDER BY region, address, house_number
        """

        cursor.execute(query, (f"%{address}%", house_number))
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return results if results else None

    except Exception as e:
        print(f"Помилка пошуку: {e}")
        return None


def search_houses_by_street(address: str) -> Optional[List[Dict]]:
    """
    Шукає всі будинки на вулиці

    Args:
        address: Назва вулиці

    Returns:
        Список знайдених будинків або None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT * FROM houses 
            WHERE address LIKE %s
            ORDER BY region, house_number
            LIMIT 50
        """

        cursor.execute(query, (f"%{address}%",))
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return results if results else None

    except Exception as e:
        print(f"Помилка пошуку: {e}")
        return None


def search_houses_by_region(region: str) -> Optional[List[Dict]]:
    """
    Шукає будинки за районом

    Args:
        region: Назва району

    Returns:
        Список знайдених будинків або None
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT * FROM houses 
            WHERE region = %s
            ORDER BY address, house_number
            LIMIT 100
        """

        cursor.execute(query, (region,))
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return results if results else None

    except Exception as e:
        print(f"Помилка пошуку: {e}")
        return None


def format_house_info(house: Dict) -> str:
    """
    Форматує інформацію про будинок для відображення

    Args:
        house: Словник з даними про будинок

    Returns:
        Відформатований текст
    """
    lines = [
        f"🏠 **{house['address']}, {house['house_number']}**",
        f"📍 **Район:** {house['region']}",
        ""
    ]

    # Проєкт
    if house.get('project'):
        lines.append(f"🏗 **Проєкт:** {house['project']}")

    # Рік будівництва
    if house.get('build_year'):
        lines.append(f"📅 **Рік будівництва:** {house['build_year']}")

    # Матеріал
    if house.get('material'):
        lines.append(f"🧱 **Матеріал:** {house['material']}")

    # Поверховість
    if house.get('floors'):
        lines.append(f"🏢 **Поверховість:** {house['floors']}")

    # Висота стелі
    if house.get('ceiling_height'):
        ceiling = house['ceiling_height']
        if ceiling and not ceiling.endswith('м'):
            ceiling = f"{ceiling} м"
        lines.append(f"📏 **Висота стелі:** {ceiling}")

    return '\n'.join(lines)


def get_total_houses_count() -> int:
    """
    Отримує загальну кількість будинків в базі

    Returns:
        Кількість будинків
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM houses")
        count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return count

    except Exception as e:
        print(f"Помилка отримання кількості: {e}")
        return 0


def get_houses_count_by_region() -> Dict[str, int]:
    """
    Отримує кількість будинків по районах

    Returns:
        Словник {район: кількість}
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            SELECT region, COUNT(*) as count 
            FROM houses 
            GROUP BY region
            ORDER BY region
        """

        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        return {row[0]: row[1] for row in results}

    except Exception as e:
        print(f"Помилка отримання статистики: {e}")
        return {}


def parse_address_input(text: str) -> tuple:
    # Видаляємо зайві пробіли
    text = ' '.join(text.split())

    # Видаляємо "вул.", "вулиця", "проспект" тощо
    text = re.sub(r'\b(вул\.|вулиця|просп\.|проспект|бульв\.|бульвар|пров\.|провулок)\b', '', text, flags=re.IGNORECASE)
    text = text.strip()

    # Видаляємо коми
    text = text.replace(',', ' ')

    # Розділяємо на частини
    parts = text.split()

    if not parts:
        return (None, None)

    # Якщо останній елемент схожий на номер будинку
    if parts[-1] and (parts[-1][0].isdigit() or '/' in parts[-1]):
        house_number = parts[-1]
        street = ' '.join(parts[:-1])
        return (street, house_number)
    else:
        # Тільки назва вулиці
        return (' '.join(parts), None)


def search_house(text: str):

    street, house_number = parse_address_input(text)

    if not street:
        return None

    # Якщо вказано номер будинку - шукаємо точну адресу
    if house_number:
        return search_house_by_address(street, house_number)
    else:
        # Тільки вулиця - шукаємо всі будинки
        return search_houses_by_street(street)