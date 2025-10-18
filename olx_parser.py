"""
Модуль для парсингу фотографій з OLX
Завантажує HTML сторінки та витягує URL-и зображень
"""

import re
import json
import requests
from bs4 import BeautifulSoup


def download_olx_photos(url):
    """
    Завантажує фотографії з OLX оголошення

    Args:
        url (str): Посилання на оголошення OLX

    Returns:
        list: Список URL-ів фотографій
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Шукаємо всі зображення в різних можливих місцях
        photo_urls = []

        # Метод 1: Шукаємо в JSON-LD структурі
        photo_urls.extend(_parse_json_ld(soup))

        # Метод 2: Шукаємо img теги з data-src або src
        photo_urls.extend(_parse_img_tags(soup))

        # Метод 3: Шукаємо в атрибутах data-*
        photo_urls.extend(_parse_data_attributes(soup))

        # Очищаємо і унікалізуємо URL-и
        clean_urls = _clean_and_deduplicate_urls(photo_urls)

        return clean_urls[:50]  # Максимум 50 фото

    except Exception as e:
        print(f"Помилка завантаження OLX: {e}")
        return []


def _parse_json_ld(soup):
    """
    Парсить JSON-LD структури на сторінці

    Args:
        soup: BeautifulSoup об'єкт

    Returns:
        list: Список знайдених URL-ів
    """
    photo_urls = []
    scripts = soup.find_all('script', type='application/ld+json')

    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and 'image' in data:
                images = data['image']
                if isinstance(images, list):
                    photo_urls.extend(images)
                elif isinstance(images, str):
                    photo_urls.append(images)
        except:
            pass

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

    for img in soup.find_all('img'):
        src = img.get('data-src') or img.get('src')
        if src and ('apollo' in src or 'olxcdn' in src or 'img.lunnapix' in src):
            # Замінюємо маленькі зображення на великі
            src = re.sub(r';s=\d+x\d+', ';s=1920x1080', src)
            src = re.sub(r'\{width\}x\{height\}', '1920x1080', src)
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
    gallery_divs = soup.find_all(['div', 'li'], attrs={'data-cy': True})

    for div in gallery_divs:
        for attr in div.attrs:
            if 'image' in attr.lower() or 'photo' in attr.lower():
                value = div[attr]
                if isinstance(value, str) and value.startswith('http'):
                    photo_urls.append(value)

    return photo_urls


def _clean_and_deduplicate_urls(photo_urls):
    """
    Очищає та видаляє дублікати з URL-ів

    Args:
        photo_urls (list): Список URL-ів для очищення

    Returns:
        list: Очищений список унікальних URL-ів
    """
    clean_urls = []

    for url in photo_urls:
        if url and url.startswith('http'):
            # Отримуємо найбільший розмір
            url = re.sub(r';s=\d+x\d+', ';s=1920x1080', url)
            if url not in clean_urls:
                clean_urls.append(url)

    return clean_urls