"""
Конфігураційний файл
"""

# Шлях до файлу з водяним знаком
WATERMARK_PATH = "watermark.png"

# Мінімальний розмір фото (пікселі)
MIN_IMAGE_SIZE = 600

# Якість збереження JPEG (1-100)
JPEG_QUALITY = 95

# Розмір водяного знаку (% від ширини фото)
WATERMARK_SIZE_PERCENT = 0.4

# Максимальна кількість фото з OLX
MAX_PHOTOS_FROM_OLX = 50

# Таймаут для HTTP запитів (секунди)
REQUEST_TIMEOUT = 10

# User-Agent для запитів
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
