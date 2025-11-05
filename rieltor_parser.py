"""
Модуль для парсингу фотографій та параметрів з Rieltor.ua
"""

import re
import json
import requests
from bs4 import BeautifulSoup


def download_rieltor_photos(url):
    """
    Завантажує фотографії з оголошення Rieltor.ua
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://rieltor.ua/'
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Шукаємо всі зображення в різних можливих місцях
        photo_urls = []

        # Метод 1: Шукаємо в JSON структурах
        photo_urls.extend(_parse_json_data(soup))

        # Метод 2: Шукаємо в галереї зображень
        photo_urls.extend(_parse_gallery(soup))

        # Метод 3: Шукаємо img теги з певними класами
        photo_urls.extend(_parse_img_tags(soup))

        # Метод 4: Шукаємо в data-атрибутах
        photo_urls.extend(_parse_data_attributes(soup))

        # Очищаємо і унікалізуємо URL-и
        clean_urls = _clean_and_deduplicate_urls(photo_urls)

        return clean_urls[:50]  # Максимум 50 фото

    except Exception as e:
        print(f"Помилка завантаження Rieltor.ua: {e}")
        return []


def parse_rieltor_parameters(url):
    """
    Парсить параметри квартири з оголошення Rieltor.ua
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://rieltor.ua/'
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        parameters = {}

        # Шукаємо контейнер з деталями оголошення
        details_container = soup.find('div', class_='offer-view-details')

        if details_container:
            # Шукаємо колонки з параметрами
            columns = details_container.find_all('div', class_='offer-view-details-column')

            for column in columns:
                text = column.get_text(strip=True)

                # Парсимо формат "Н кімнати"
                rooms_match = re.search(r'(\d+)\s*кімнат', text, re.IGNORECASE)
                if rooms_match:
                    parameters['Кількість кімнат'] = rooms_match.group(1)

                # Парсимо формат "Н/Н/Н м²" (загальна/житлова/кухня)
                areas_match = re.search(r'(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*м²', text)
                if areas_match:
                    parameters['Загальна площа'] = areas_match.group(1) + ' м²'
                    parameters['Житлова площа'] = areas_match.group(2) + ' м²'
                    parameters['Площа кухні'] = areas_match.group(3) + ' м²'

                # Парсимо формат "поверх Н з Н"
                floor_match = re.search(r'поверх\s+(\d+)\s+з\s+(\d+)', text, re.IGNORECASE)
                if floor_match:
                    parameters['Поверх'] = floor_match.group(1)
                    parameters['Поверховість'] = floor_match.group(2)

                # Тип будинку
                if 'Тип будинку' in text or 'будинок' in text.lower():
                    building_types = ['Цегляний', 'Панельний', 'Монолітний', 'Блочний']
                    for building_type in building_types:
                        if building_type.lower() in text.lower():
                            parameters['Тип будинку'] = building_type
                            break

                # Тип стін
                if 'Тип стін' in text or 'стін' in text.lower():
                    wall_types = ['Цегляний', 'Панельний', 'Монолітний', 'Блочний']
                    for wall_type in wall_types:
                        if wall_type.lower() in text.lower():
                            parameters['Тип стін'] = wall_type
                            break

                # Ремонт
                if 'Ремонт' in text or 'ремонт' in text.lower():
                    repair_types = ['Євроремонт', 'Косметичний', 'Без ремонту', 'Дизайнерський', 'Потребує ремонту']
                    for repair_type in repair_types:
                        if repair_type.lower() in text.lower():
                            parameters['Ремонт'] = repair_type
                            break

                # Меблювання
                if 'Меблі' in text or 'меблюван' in text.lower():
                    if 'так' in text.lower() or 'є' in text.lower():
                        parameters['Меблювання'] = 'Так'
                    elif 'ні' in text.lower() or 'немає' in text.lower():
                        parameters['Меблювання'] = 'Ні'

        # Додатковий пошук у всій сторінці якщо не знайшли параметри
        if not parameters:
            all_text = soup.get_text()

            # Кількість кімнат
            rooms_match = re.search(r'(\d+)[-\s]*кімнат', all_text, re.IGNORECASE)
            if rooms_match:
                parameters['Кількість кімнат'] = rooms_match.group(1)

            # Площі
            areas_match = re.search(r'(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*м²', all_text)
            if areas_match:
                parameters['Загальна площа'] = areas_match.group(1) + ' м²'
                parameters['Житлова площа'] = areas_match.group(2) + ' м²'
                parameters['Площа кухні'] = areas_match.group(3) + ' м²'

            # Поверх
            floor_match = re.search(r'поверх\s+(\d+)\s+з\s+(\d+)', all_text, re.IGNORECASE)
            if floor_match:
                parameters['Поверх'] = floor_match.group(1)
                parameters['Поверховість'] = floor_match.group(2)

        return parameters

    except Exception as e:
        print(f"Помилка парсингу параметрів Rieltor.ua: {e}")
        return {}


def _parse_json_data(soup):
    """
    Парсить JSON дані на сторінці
    """
    photo_urls = []

    # Шукаємо script теги з JSON
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                # Шукаємо image поля
                if 'image' in data:
                    images = data['image']
                    if isinstance(images, list):
                        photo_urls.extend(images)
                    elif isinstance(images, str):
                        photo_urls.append(images)
        except:
            pass

    # Шукаємо JavaScript змінні з URL-ами
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            # Шукаємо масиви з URL-ами зображень
            matches = re.findall(r'https?://[^\s"\']+\.(?:jpg|jpeg|png|webp)', script.string)
            photo_urls.extend(matches)

    return photo_urls


def _parse_gallery(soup):
    """
    Парсить галерею зображень на сторінці
    """
    photo_urls = []

    # Шукаємо елементи галереї
    gallery_selectors = [
        'div[class*="gallery"]',
        'div[class*="slider"]',
        'div[class*="photo"]',
        'div[id*="gallery"]',
        'ul[class*="gallery"]',
        'div[class*="image-list"]'
    ]

    for selector in gallery_selectors:
        gallery_elements = soup.select(selector)
        for element in gallery_elements:
            # Шукаємо всі img теги всередині
            imgs = element.find_all('img')
            for img in imgs:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src:
                    photo_urls.append(src)

    return photo_urls


def _parse_img_tags(soup):
    """
    Парсить IMG теги на сторінці
    """
    photo_urls = []

    # Шукаємо img теги з певними характеристиками
    for img in soup.find_all('img'):
        # Перевіряємо різні атрибути
        src = (img.get('src') or
               img.get('data-src') or
               img.get('data-lazy') or
               img.get('data-original'))

        if src:
            # Фільтруємо тільки зображення оголошень
            if any(keyword in src for keyword in ['rieltor.ua', 'estate', 'flats', 'realty']):
                src = _maximize_image_size(src)
                photo_urls.append(src)

    return photo_urls


def _parse_data_attributes(soup):
    photo_urls = []

    # Шукаємо елементи з data-атрибутами
    elements = soup.find_all(['div', 'a', 'li', 'span'])
    for element in elements:
        for attr in element.attrs:
            if 'image' in attr.lower() or 'photo' in attr.lower() or 'src' in attr.lower():
                value = element[attr]
                if isinstance(value, str) and value.startswith('http'):
                    photo_urls.append(value)

    return photo_urls


def _maximize_image_size(url):
    """
    Змінює URL зображення для отримання максимального розміру
    """
    # Видаляємо параметри розміру
    url = re.sub(r'_\d+x\d+', '', url)
    url = re.sub(r'/\d+x\d+/', '/original/', url)
    url = re.sub(r'thumb_\d+', 'original', url)

    # Замінюємо розміри на великі
    url = re.sub(r'w=\d+', 'w=1920', url)
    url = re.sub(r'h=\d+', 'h=1080', url)

    return url


def _clean_and_deduplicate_urls(photo_urls):
    """
    Очищає та видаляє дублікати з URL-ів
    """
    clean_urls = []
    seen_urls = set()

    for url in photo_urls:
        if not url:
            continue

        # Перевіряємо чи це валідний URL зображення
        if not url.startswith('http'):
            continue

        # Ігноруємо іконки, логотипи та маленькі зображення
        if any(keyword in url.lower() for keyword in ['logo', 'icon', 'avatar', 'banner']):
            continue

        # Перевіряємо розширення файлу
        if not re.search(r'\.(jpg|jpeg|png|webp)', url, re.IGNORECASE):
            continue

        # Максимізуємо розмір
        url = _maximize_image_size(url)

        # Видаляємо параметри запиту для порівняння
        url_base = url.split('?')[0]

        if url_base not in seen_urls:
            seen_urls.add(url_base)
            clean_urls.append(url)

    return clean_urls


def is_rieltor_url(url):
    """
    Перевіряє чи є URL посиланням на Rieltor.ua
    """
    return bool(re.match(r'https?://(?:www\.)?rieltor\.ua/', url))