"""
Модуль для парсингу фотографій з LUN.ua
Завантажує HTML сторінки та витягує URL-и зображень
"""

import re
import json
import requests
from bs4 import BeautifulSoup


def download_lun_photos(url):
    """
    Завантажує фотографії з оголошення LUN.ua

    Args:
        url (str): Посилання на оголошення LUN.ua

    Returns:
        list: Список URL-ів фотографій
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://lun.ua/'
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

        # Метод 5: Шукаємо в JavaScript змінних
        photo_urls.extend(_parse_js_variables(soup))

        # Очищаємо і унікалізуємо URL-и
        clean_urls = _clean_and_deduplicate_urls(photo_urls)

        return clean_urls[:50]  # Максимум 50 фото

    except Exception as e:
        print(f"Помилка завантаження LUN.ua: {e}")
        return []


def _parse_json_data(soup):
    """
    Парсить JSON дані на сторінці

    Args:
        soup: BeautifulSoup об'єкт

    Returns:
        list: Список знайдених URL-ів
    """
    photo_urls = []

    # Шукаємо script теги з JSON-LD
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

    # Шукаємо звичайні script теги з JSON
    scripts = soup.find_all('script', type='application/json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            # Рекурсивно шукаємо URL-и зображень
            _extract_images_from_json(data, photo_urls)
        except:
            pass

    return photo_urls


def _extract_images_from_json(data, photo_urls):
    """
    Рекурсивно витягує URL-и зображень з JSON структури

    Args:
        data: JSON дані (dict, list, або інше)
        photo_urls (list): Список для додавання знайдених URL-ів
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(key, str) and any(k in key.lower() for k in ['image', 'photo', 'picture', 'img']):
                if isinstance(value, str) and value.startswith('http'):
                    photo_urls.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.startswith('http'):
                            photo_urls.append(item)
            _extract_images_from_json(value, photo_urls)
    elif isinstance(data, list):
        for item in data:
            _extract_images_from_json(item, photo_urls)


def _parse_js_variables(soup):
    """
    Парсить JavaScript змінні на сторінці

    Args:
        soup: BeautifulSoup об'єкт

    Returns:
        list: Список знайдених URL-ів
    """
    photo_urls = []

    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            # Шукаємо URL-и зображень в JS коді
            matches = re.findall(r'https?://[^\s"\']+\.(?:jpg|jpeg|png|webp)', script.string)
            for match in matches:
                if 'lun.ua' in match or 'img' in match or 'photo' in match:
                    photo_urls.append(match)

    return photo_urls


def _parse_gallery(soup):
    """
    Парсить галерею зображень на сторінці

    Args:
        soup: BeautifulSoup об'єкт

    Returns:
        list: Список знайдених URL-ів
    """
    photo_urls = []

    # Шукаємо елементи галереї
    gallery_selectors = [
        'div[class*="gallery"]',
        'div[class*="slider"]',
        'div[class*="photo"]',
        'div[id*="gallery"]',
        'ul[class*="gallery"]',
        'div[class*="image"]',
        'div[class*="swiper"]',
        'section[class*="photo"]'
    ]

    for selector in gallery_selectors:
        gallery_elements = soup.select(selector)
        for element in gallery_elements:
            # Шукаємо всі img теги всередині
            imgs = element.find_all('img')
            for img in imgs:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy') or img.get('data-original')
                if src:
                    photo_urls.append(src)

            # Також шукаємо в background-image стилях
            style = element.get('style')
            if style:
                bg_matches = re.findall(r'url\(["\']?(https?://[^"\']+)["\']?\)', style)
                photo_urls.extend(bg_matches)

    return photo_urls


def _parse_img_tags(soup):
    """
    Парсить IMG теги на сторінці

    Args:
        soup: BeautifulSoup об'єкт

    Returns:
        list: Список знайдених URL-ів
    """
    photo_urls = []

    # Шукаємо img теги з певними характеристиками
    for img in soup.find_all('img'):
        # Перевіряємо різні атрибути
        src = (img.get('src') or
               img.get('data-src') or
               img.get('data-lazy') or
               img.get('data-original') or
               img.get('data-srcset'))

        if src:
            # Якщо це srcset, беремо найбільше зображення
            if 'data-srcset' in img.attrs:
                srcset = img.get('data-srcset')
                urls = re.findall(r'(https?://[^\s,]+)', srcset)
                if urls:
                    src = urls[-1]  # Беремо останній (зазвичай найбільший)

            # Фільтруємо тільки зображення оголошень
            if any(keyword in src.lower() for keyword in ['lun.ua', 'estate', 'realty', 'img', 'photo']):
                # Змінюємо розмір на максимальний
                src = _maximize_image_size(src)
                photo_urls.append(src)

    return photo_urls


def _parse_data_attributes(soup):
    """
    Парсить data-* атрибути на сторінці

    Args:
        soup: BeautifulSoup об'єкт

    Returns:
        list: Список знайдених URL-ів
    """
    photo_urls = []

    # Шукаємо елементи з data-атрибутами
    elements = soup.find_all(['div', 'a', 'li', 'span', 'section'])
    for element in elements:
        for attr in element.attrs:
            if any(keyword in attr.lower() for keyword in ['image', 'photo', 'src', 'picture', 'img']):
                value = element[attr]
                if isinstance(value, str) and value.startswith('http'):
                    photo_urls.append(value)
                elif isinstance(value, str) and value.startswith('/'):
                    # Додаємо домен якщо це відносний шлях
                    photo_urls.append(f"https://lun.ua{value}")

    return photo_urls


def _maximize_image_size(url):
    """
    Змінює URL зображення для отримання максимального розміру

    Args:
        url (str): Оригінальний URL зображення

    Returns:
        str: URL з максимальним розміром
    """
    # Видаляємо параметри розміру
    url = re.sub(r'_\d+x\d+', '', url)
    url = re.sub(r'/\d+x\d+/', '/original/', url)
    url = re.sub(r'thumb_\d+', 'original', url)
    url = re.sub(r'small_\d+', 'original', url)
    url = re.sub(r'medium_\d+', 'original', url)

    # Замінюємо розміри на великі
    url = re.sub(r'w=\d+', 'w=2048', url)
    url = re.sub(r'h=\d+', 'h=2048', url)
    url = re.sub(r'width=\d+', 'width=2048', url)
    url = re.sub(r'height=\d+', 'height=2048', url)

    # Замінюємо якість на максимальну
    url = re.sub(r'q=\d+', 'q=100', url)
    url = re.sub(r'quality=\d+', 'quality=100', url)

    return url


def _clean_and_deduplicate_urls(photo_urls):
    """
    Очищає та видаляє дублікати з URL-ів

    Args:
        photo_urls (list): Список URL-ів для очищення

    Returns:
        list: Очищений список унікальних URL-ів
    """
    clean_urls = []
    seen_urls = set()

    for url in photo_urls:
        if not url:
            continue

        # Перевіряємо чи це валідний URL зображення
        if not url.startswith('http'):
            # Додаємо домен якщо це відносний шлях
            if url.startswith('/'):
                url = f"https://lun.ua{url}"
            else:
                continue

        # Ігноруємо іконки, логотипи та маленькі зображення
        if any(keyword in url.lower() for keyword in ['logo', 'icon', 'avatar', 'banner', 'btn', 'button']):
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


def is_lun_url(url):
    """
    Перевіряє чи є URL посиланням на LUN.ua

    Args:
        url (str): URL для перевірки

    Returns:
        bool: True якщо це LUN.ua, False якщо ні
    """
    return bool(re.match(r'https?://(?:www\.)?lun\.ua/', url))