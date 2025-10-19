"""
Модуль для парсингу будинків з my-realty.kiev.ua
"""

import requests
from bs4 import BeautifulSoup
import re
from database import get_connection


# Список районів Києва
DISTRICTS = {
    'Голосіївський': 'https://my-realty.kiev.ua/uk/houses/goloseevskyj-rajon-8',
    'Дарницький': 'https://my-realty.kiev.ua/uk/houses/darnyczkyj-rajon-7',
    'Деснянський': 'https://my-realty.kiev.ua/uk/houses/desnyanskyj-rajon-9',
    'Дніпровський': 'https://my-realty.kiev.ua/uk/houses/dneprovskyj-rajon-2',
    'Оболонський': 'https://my-realty.kiev.ua/uk/houses/obolonskyj-rajon-1',
    'Печерський': 'https://my-realty.kiev.ua/uk/houses/pecherskyj-rajon-3',
    'Подільський': 'https://my-realty.kiev.ua/uk/houses/podolskyj-rajon-5',
    'Святошинський': 'https://my-realty.kiev.ua/uk/houses/svyatoshynskyj-rajon-10',
    'Солом\'янський': 'https://my-realty.kiev.ua/uk/houses/solomenskyj-rajon-4',
    'Шевченківський': 'https://my-realty.kiev.ua/uk/houses/shevchenkovskyj-rajon-6'
}


def create_houses_table():
    """
    Створює таблицю будинків якщо не існує
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS houses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                region VARCHAR(50) NOT NULL,
                address VARCHAR(255) NOT NULL,
                house_number VARCHAR(20) NOT NULL,
                project VARCHAR(150),
                build_year VARCHAR(50),
                material VARCHAR(500),
                floors VARCHAR(100),
                ceiling_height VARCHAR(50),
                INDEX idx_region (region),
                INDEX idx_address (address),
                INDEX idx_full_address (address, house_number)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cursor.close()
        conn.close()

        print("✅ Таблиця houses готова")
        return True
    except Exception as e:
        print(f"❌ Помилка створення таблиці houses: {e}")
        return False


def extract_houses_from_page(html_content, region_name):
    """
    Витягує дані про будинки з HTML сторінки

    Парсить блоки <div class="col-xs-12 col-md-6 houseBlock">
    """
    houses = []

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Знаходимо всі блоки з будинками
        house_blocks = soup.find_all('div', class_='houseBlock')

        if not house_blocks:
            print(f"⚠️ Не знайдено блоків houseBlock для {region_name}")
            return houses

        print(f"  Знайдено {len(house_blocks)} блоків будинків")

        for block in house_blocks:
            try:
                # Отримуємо назву вулиці та номер будинку з <h3>
                h3_tag = block.find('h3')
                if not h3_tag:
                    continue

                a_tag = h3_tag.find('a')
                if not a_tag:
                    continue

                # Повна адреса: "Ломоносова вулиця 4"
                full_address = a_tag.get_text(strip=True)

                # Розділяємо на вулицю і номер
                # Останнє слово - номер будинку
                parts = full_address.rsplit(' ', 1)
                if len(parts) != 2:
                    continue

                street = parts[0]  # "Ломоносова вулиця"
                house_num = parts[1]  # "4"

                # Знаходимо таблицю з характеристиками
                table = block.find('table', class_='table-striped')
                if not table:
                    # Додаємо хоча б адресу
                    houses.append({
                        'region': region_name,
                        'address': street,
                        'house_number': house_num,
                        'project': '',
                        'build_year': '',
                        'material': '',
                        'floors': '',
                        'ceiling_height': ''
                    })
                    continue

                # Парсимо дані з таблиці
                house_data = {
                    'region': region_name,
                    'address': street,
                    'house_number': house_num,
                    'project': '',
                    'build_year': '',
                    'material': '',
                    'floors': '',
                    'ceiling_height': ''
                }

                # Проходимо по всіх рядках таблиці
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) != 2:
                        continue

                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)

                    # Витягуємо тільки текст, без посилань
                    if cells[1].find('a'):
                        value = cells[1].find('a').get_text(strip=True)

                    # Маппінг полів
                    if 'Проєкт' in label or 'Проект' in label:
                        house_data['project'] = value
                    elif 'Рік будівництва' in label:
                        house_data['build_year'] = value
                    elif 'Матеріал' in label:
                        house_data['material'] = value
                    elif 'Поверховість' in label:
                        house_data['floors'] = value
                    elif 'Висота стелі' in label:
                        house_data['ceiling_height'] = value

                houses.append(house_data)

            except Exception as e:
                print(f"  ⚠️ Помилка обробки блоку будинку: {e}")
                continue

        return houses

    except Exception as e:
        print(f"❌ Помилка парсингу для {region_name}: {e}")
        return houses


def get_total_pages(url):
    """
    Отримує загальну кількість сторінок для району
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        # Шукаємо totalPages в JavaScript
        pattern = r"var totalPages\s*=\s*['\"](\d+)['\"];"
        match = re.search(pattern, response.text)

        if match:
            return int(match.group(1))

        return 1

    except Exception as e:
        print(f"⚠️ Не вдалося отримати кількість сторінок: {e}")
        return 1


def parse_district(district_name, base_url, progress_data=None):
    """
    Парсить всі сторінки одного району

    Args:
        district_name: Назва району
        base_url: Базовий URL району
        progress_data: Словник для збереження прогресу {'district': '', 'page': 0, 'total': 0, 'found': 0}
    """
    print(f"\n🔍 Парсинг району: {district_name}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    all_houses = []

    try:
        # Отримуємо загальну кількість сторінок
        total_pages = get_total_pages(base_url)
        print(f"📄 Всього сторінок: {total_pages}")

        # Парсимо кожну сторінку
        for page in range(1, total_pages + 1):
            try:
                # Формуємо URL сторінки
                if page == 1:
                    page_url = base_url
                else:
                    page_url = f"{base_url}?page={page}"

                # Завантажуємо сторінку
                response = requests.get(page_url, headers=headers, timeout=15)
                response.raise_for_status()

                # Витягуємо будинки
                houses = extract_houses_from_page(response.text, district_name)
                all_houses.extend(houses)

                # Оновлюємо прогрес
                if progress_data is not None:
                    progress_data['district'] = district_name
                    progress_data['page'] = page
                    progress_data['total'] = total_pages
                    progress_data['found'] = len(houses)
                else:
                    print(f"  Сторінка {page}/{total_pages}: знайдено {len(houses)} будинків")

            except Exception as e:
                print(f"  ❌ Помилка на сторінці {page}: {e}")
                continue

        print(f"✅ {district_name}: знайдено {len(all_houses)} будинків")
        return all_houses

    except Exception as e:
        print(f"❌ Помилка парсингу району {district_name}: {e}")
        return all_houses


def save_houses_to_db(houses):
    """
    Зберігає будинки в базу даних
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Очищуємо таблицю перед оновленням
        cursor.execute("TRUNCATE TABLE houses")

        # Вставляємо дані пакетами
        insert_query = """
            INSERT INTO houses 
            (region, address, house_number, project, build_year, material, floors, ceiling_height)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = [
            (
                house['region'],
                house['address'],
                house['house_number'],
                house['project'],
                house['build_year'],
                house['material'],
                house['floors'],
                house['ceiling_height']
            )
            for house in houses
        ]

        cursor.executemany(insert_query, values)
        conn.commit()

        cursor.close()
        conn.close()

        print(f"\n✅ Збережено {len(houses)} будинків в базу даних")
        return True

    except Exception as e:
        print(f"❌ Помилка збереження в БД: {e}")
        return False


def parse_all_districts(progress_callback=None):
    """
    Парсить всі райони Києва
    """
    print("🚀 Початок парсингу всіх районів Києва\n")

    all_houses = []

    for district_name, base_url in DISTRICTS.items():
        houses = parse_district(district_name, base_url, progress_callback)
        all_houses.extend(houses)

    print(f"\n📊 Всього знайдено будинків: {len(all_houses)}")

    # Зберігаємо в базу даних
    if all_houses:
        save_houses_to_db(all_houses)

    return len(all_houses)


if __name__ == '__main__':
    # Тестовий запуск
    create_houses_table()
    parse_all_districts()