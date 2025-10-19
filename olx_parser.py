"""
Модуль для парсингу фотографій та параметрів з OLX
"""

import re
import json
import requests
from bs4 import BeautifulSoup


def download_olx_photos(url):
    """
    Завантажує фотографії з OLX оголошення
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


def parse_olx_parameters(url):
    """
    Парсить параметри квартири з оголошення OLX
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        parameters = {}

        # Шукаємо контейнер з параметрами
        params_container = soup.find('div', {'data-testid': 'ad-parameters-container'})

        if params_container:
            # Знаходимо всі параграфи з класом css-13x8d99
            all_paragraphs = params_container.find_all('p', class_='css-13x8d99')

            # Кожен <p> містить пару "Назва: Значення"
            for para in all_paragraphs:
                text = para.get_text(strip=True)

                # Розділяємо по двокрапці
                if ':' in text:
                    parts = text.split(':', 1)
                    if len(parts) == 2:
                        param_name = parts[0].strip()
                        param_value = parts[1].strip()

                        # Обробляємо різні параметри
                        if 'Загальна площа' in param_name:
                            parameters['Загальна площа'] = param_value

                        elif 'Площа кухні' in param_name:
                            parameters['Площа кухні'] = param_value

                        elif 'Тип будинку' in param_name:
                            parameters['Тип будинку'] = param_value

                        elif 'Поверх' == param_name:
                            # Може бути "5" або "5 з 9"
                            if 'з' in param_value:
                                # Формат "5 з 9"
                                parts_floor = param_value.split('з')
                                if len(parts_floor) == 2:
                                    parameters['Поверх'] = parts_floor[0].strip()
                                    parameters['Поверховість'] = parts_floor[1].strip()
                            else:
                                parameters['Поверх'] = param_value

                        elif 'Поверховість' in param_name:
                            if 'Поверховість' not in parameters:
                                parameters['Поверховість'] = param_value

                        elif 'Тип стін' in param_name:
                            parameters['Тип стін'] = param_value

                        elif 'Кількість кімнат' in param_name:
                            parameters['Кількість кімнат'] = param_value

                        elif 'Ремонт' in param_name:
                            parameters['Ремонт'] = param_value

                        elif 'Меблювання' in param_name or 'Меблі' in param_name:
                            # Перетворюємо на Так/Ні
                            value_lower = param_value.lower()
                            if 'так' in value_lower:
                                parameters['Меблювання'] = 'Так'
                            elif 'ні' in value_lower:
                                parameters['Меблювання'] = 'Ні'
                            else:
                                parameters['Меблювання'] = param_value

        # Додатковий пошук якщо не знайшли параметри у стандартному контейнері
        if not parameters:
            # Шукаємо всі p елементи на сторінці
            all_paragraphs = soup.find_all('p')

            for i, para in enumerate(all_paragraphs):
                text = para.get_text(strip=True)

                # Шукаємо пару назва-значення
                if i + 1 < len(all_paragraphs):
                    next_text = all_paragraphs[i + 1].get_text(strip=True)

                    # Загальна площа
                    if 'Загальна площа' in text and 'Загальна площа' not in parameters:
                        if 'м²' in next_text or re.search(r'\d+', next_text):
                            parameters['Загальна площа'] = next_text

                    # Площа кухні
                    elif 'Площа кухні' in text and 'Площа кухні' not in parameters:
                        if 'м²' in next_text or re.search(r'\d+', next_text):
                            parameters['Площа кухні'] = next_text

                    # Кількість кімнат
                    elif 'Кількість кімнат' in text and 'Кількість кімнат' not in parameters:
                        parameters['Кількість кімнат'] = next_text

                    # Поверх
                    elif 'Поверх' in text and 'Поверховість' not in text and 'Поверх' not in parameters:
                        parameters['Поверх'] = next_text

        return parameters

    except Exception as e:
        print(f"Помилка парсингу параметрів OLX: {e}")
        return {}


def _parse_json_ld(soup):
    """
    Парсить JSON-LD структури на сторінці
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
    """
    clean_urls = []

    for url in photo_urls:
        if url and url.startswith('http'):
            # Отримуємо найбільший розмір
            url = re.sub(r';s=\d+x\d+', ';s=1920x1080', url)
            if url not in clean_urls:
                clean_urls.append(url)

    return clean_urls