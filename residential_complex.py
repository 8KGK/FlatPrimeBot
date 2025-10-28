"""
Модуль для роботи з базою даних ЖК (Житлових Комплексів)
"""

from database import get_connection


def create_residential_complexes_table():
    """Створює таблицю для зберігання ЖК"""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS residential_complexes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            url VARCHAR(500) NOT NULL,
            bank VARCHAR(50) NOT NULL,
            class VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_bank (bank),
            INDEX idx_class (class)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    connection.commit()
    cursor.close()
    connection.close()


def add_residential_complex(name, url, bank, class_type):
    """
    Додає новий ЖК до бази даних

    Args:
        name: Назва ЖК
        url: Посилання на ЖК
        bank: Берег (Лівий берег / Правий берег)
        class_type: Клас (Економ/Комфорт / Бізнес / Преміум)

    Returns:
        True якщо успішно, False якщо помилка
    """
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO residential_complexes (name, url, bank, class)
            VALUES (%s, %s, %s, %s)
        """, (name, url, bank, class_type))

        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print(f"Помилка додавання ЖК: {e}")
        return False


def get_residential_complexes_by_bank_and_class(bank, class_type):
    """
    Отримує список ЖК за берегом та класом

    Args:
        bank: Берег (Лівий берег / Правий берег)
        class_type: Клас (Економ/Комфорт / Бізнес / Преміум)

    Returns:
        Список словників з інформацією про ЖК
    """
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, url, bank, class
            FROM residential_complexes
            WHERE bank = %s AND class = %s
            ORDER BY name
        """, (bank, class_type))

        results = cursor.fetchall()
        cursor.close()
        connection.close()
        return results
    except Exception as e:
        print(f"Помилка отримання ЖК: {e}")
        return []


def get_all_residential_complexes():
    """Отримує всі ЖК з бази даних"""
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name, url, bank, class
            FROM residential_complexes
            ORDER BY bank, class, name
        """)

        results = cursor.fetchall()
        cursor.close()
        connection.close()
        return results
    except Exception as e:
        print(f"Помилка отримання всіх ЖК: {e}")
        return []


def delete_residential_complex(rc_id):
    """Видаляє ЖК з бази даних"""
    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM residential_complexes
            WHERE id = %s
        """, (rc_id,))

        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print(f"Помилка видалення ЖК: {e}")
        return False


def initialize_default_complexes():
    """
    Додає початкові ЖК до бази даних
    Викликається один раз при першому запуску
    """
    # Перевіряємо чи база порожня
    complexes = get_all_residential_complexes()
    if complexes:
        print("ℹ️  База ЖК вже містить дані")
        return

    # Початкові дані
    default_complexes = [
        # Лівий берег
        ("ЖК Зарічний", "https://lun.ua/uk/жк-зарічний-київ", "Лівий берег", "Бізнес"),
        ("ЖК Севен", "https://lun.ua/uk/жк-seven-київ", "Лівий берег", "Економ/Комфорт"),
        ("ЖК RiverStone", "https://lun.ua/uk/жк-riverstone-київ", "Лівий берег", "Преміум"),

        # Правий берег
        ("ЖК Старт", "https://lun.ua/uk/жк-старт-київ", "Правий берег", "Бізнес"),
        ("ЖК UNO", "https://lun.ua/uk/жк-uno-city-house-київ", "Правий берег", "Економ/Комфорт"),
        ("ЖК ART Hall", "https://lun.ua/uk/клубний-будинок-арт-холл-київ", "Правий берег", "Преміум"),
    ]

    for name, url, bank, class_type in default_complexes:
        add_residential_complex(name, url, bank, class_type)

    print(f"✅ Додано {len(default_complexes)} початкових ЖК до бази даних")


def get_banks():
    """Повертає список доступних берегів"""
    return ["Лівий берег", "Правий берег"]


def get_classes():
    """Повертає список доступних класів"""
    return ["Економ/Комфорт", "Бізнес", "Преміум"]