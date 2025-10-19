"""
Модуль для обробки зображень
"""

import os
from PIL import Image
from config import WATERMARK_PATH


def process_single_image(image):
    """
    Обробляє одне зображення: змінює розмір та додає водяний знак
    """
    try:
        # Конвертуємо в RGB якщо потрібно
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Змінюємо розмір якщо потрібно
        image = _resize_if_needed(image)

        # Додаємо водяний знак
        image = _add_watermark(image)

        return image

    except Exception as e:
        print(f"Помилка обробки зображення: {e}")
        return None


def _resize_if_needed(image):
    """
    Змінює розмір зображення до мінімум 600x600 пікселів
    """
    width, height = image.size

    # Перевіряємо чи потрібно збільшити розмір
    if width < 600 or height < 600:
        # Знаходимо коефіцієнт збільшення
        scale = max(600 / width, 600 / height)
        new_width = int(width * scale)
        new_height = int(height * scale)

        # Збільшуємо фото зі збереженням пропорцій
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        print(f"Розмір змінено: {width}x{height} → {new_width}x{new_height}")

    return image


def _add_watermark(image):
    """
    Додає водяний знак на зображення
    """
    if not os.path.exists(WATERMARK_PATH):
        print(f"⚠️ Водяний знак не знайдено за шляхом: {WATERMARK_PATH}")
        return image

    watermark = Image.open(WATERMARK_PATH)

    # Конвертуємо водяний знак в RGBA якщо потрібно
    if watermark.mode != 'RGBA':
        watermark = watermark.convert('RGBA')

    # Розміщуємо водяний знак по центру
    # Розмір водяного знаку - 40% від ширини фото
    wm_width = int(image.width * 0.6)
    wm_ratio = wm_width / watermark.width
    wm_height = int(watermark.height * wm_ratio)

    # Змінюємо розмір водяного знаку зі збереженням пропорцій
    watermark = watermark.resize((wm_width, wm_height), Image.Resampling.LANCZOS)

    # Позиція по центру фото
    position = (
        (image.width - wm_width) // 2,
        (image.height - wm_height) // 2
    )

    # Додаємо водяний знак
    image.paste(watermark, position, watermark)

    return image


def get_watermark_size_percent():
    """
    Повертає поточний розмір водяного знаку у відсотках
    """
    return 0.4


def set_watermark_size_percent(percent):
    """
    Встановлює розмір водяного знаку у відсотках
    """
    # Ця функція для майбутнього розширення функціоналу
    pass