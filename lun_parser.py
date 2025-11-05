"""
Модуль для парсингу фотографій з LUN.ua (Selenium версія)
"""

import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def download_lun_photos(url):
    """
    Завантажує фотографії з LUN.ua використовуючи Selenium
    """
    driver = None
    try:
        print(f"🔍 Починаю парсинг LUN.ua: {url}")

        # Налаштування Chrome
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Ініціалізуємо драйвер
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)

        # Відкриваємо сторінку
        print("📄 Завантажую сторінку...")
        driver.get(url)

        # Чекаємо завантаження галереї
        try:
            print("⏳ Чекаю завантаження галереї...")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.lazyload-wrapper, div[class*='Gallery'], div[class*='gallery'], img[src*='lun.ua']"))
            )
            time.sleep(2)  # Додатковий час для JS
        except TimeoutException:
            print("⚠️ Галерея не завантажилась, пробую альтернативний метод...")

        photo_urls = set()
        photo_hashes = set()

        # Метод 1: Пошук через клік по галереї
        print("📸 Метод 1: Збір фото через прокрутку галереї...")
        max_clicks = 50
        clicks_count = 0
        no_new_photos_count = 0

        while clicks_count < max_clicks:
            # Збираємо поточні фото
            previous_count = len(photo_hashes)

            # Шукаємо всі source теги
            try:
                sources = driver.find_elements(By.TAG_NAME, "source")
                for source in sources:
                    srcset = source.get_attribute("srcset")
                    if srcset:
                        urls = _parse_srcset(srcset)
                        for img_url in urls:
                            photo_id = _get_photo_id(img_url)
                            if photo_id and photo_id not in photo_hashes:
                                photo_hashes.add(photo_id)
                                photo_urls.add(img_url)
            except Exception as e:
                print(f"Помилка пошуку source: {e}")

            # Шукаємо всі img теги
            try:
                images = driver.find_elements(By.TAG_NAME, "img")
                for img in images:
                    src = img.get_attribute("src") or img.get_attribute("data-src")
                    if src and src.startswith("http"):
                        photo_id = _get_photo_id(src)
                        if photo_id and photo_id not in photo_hashes:
                            photo_hashes.add(photo_id)
                            photo_urls.add(src)
            except Exception as e:
                print(f"Помилка пошуку img: {e}")

            # Перевіряємо чи з'явились нові фото
            if len(photo_hashes) == previous_count:
                no_new_photos_count += 1
                if no_new_photos_count >= 2:
                    print("✅ Нових фото не знайдено, завершую...")
                    break
            else:
                no_new_photos_count = 0
                print(f"📊 Знайдено {len(photo_hashes)} унікальних фото...")

            # Шукаємо кнопку "наступне фото"
            try:
                # Різні варіанти селекторів для стрілки вправо
                arrow_selectors = [
                    "div[class*='NavigationArrow']",
                    "button[class*='next']",
                    "div[class*='arrow'][class*='right']",
                    "button[aria-label*='Next']",
                    "div[class*='slider'] button:last-child"
                ]

                arrow_clicked = False
                for selector in arrow_selectors:
                    try:
                        arrows = driver.find_elements(By.CSS_SELECTOR, selector)
                        for arrow in arrows:
                            if arrow.is_displayed() and arrow.is_enabled():
                                arrow.click()
                                time.sleep(0.8)
                                arrow_clicked = True
                                clicks_count += 1
                                break
                        if arrow_clicked:
                            break
                    except:
                        continue

                if not arrow_clicked:
                    print("⚠️ Стрілка не знайдена")
                    break

            except Exception as e:
                print(f"⚠️ Помилка при кліку: {e}")
                break

        # Метод 2: Парсинг HTML коду сторінки
        print("📸 Метод 2: Пошук в HTML коді...")
        page_source = driver.page_source

        # Шукаємо URL зображень в HTML
        html_urls = re.findall(
            r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)',
            page_source,
            re.IGNORECASE
        )

        for img_url in html_urls:
            photo_id = _get_photo_id(img_url)
            if photo_id and photo_id not in photo_hashes:
                photo_hashes.add(photo_id)
                photo_urls.add(img_url)

        # Очищаємо та максимізуємо якість
        clean_urls = _clean_and_deduplicate_urls(list(photo_urls))

        print(f"✅ Знайдено {len(clean_urls)} унікальних фотографій")
        return clean_urls[:50]

    except Exception as e:
        print(f"❌ Критична помилка завантаження LUN.ua: {e}")
        import traceback
        traceback.print_exc()
        return []

    finally:
        # Закриваємо браузер
        if driver:
            try:
                driver.quit()
            except:
                pass


def _parse_srcset(srcset):
    """Парсить srcset атрибут"""
    urls = []
    if not srcset:
        return urls

    try:
        parts = srcset.split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            url_parts = part.split()
            if url_parts and url_parts[0].startswith('http'):
                urls.append(url_parts[0])
    except Exception as e:
        print(f"Помилка парсингу srcset: {e}")

    return urls


def _get_photo_id(url):
    """Отримує унікальний ідентифікатор фото"""
    if not url:
        return None

    try:
        url_base = url.split('?')[0]
        url_no_ext = re.sub(r'\.(jpg|jpeg|png|webp)$', '', url_base, flags=re.IGNORECASE)
        url_no_ext = re.sub(r'_\d+x\d+$', '', url_no_ext)
        url_no_ext = re.sub(r'/\d+x\d+$', '', url_no_ext)
        url_no_ext = re.sub(r'_w\d+$', '', url_no_ext)
        url_no_ext = re.sub(r'_h\d+$', '', url_no_ext)
        return url_no_ext
    except Exception as e:
        print(f"Помилка отримання photo_id: {e}")
        return None


def _maximize_image_size(url):
    """Максимізує розмір зображення"""
    if not url:
        return url

    try:
        url = re.sub(r'_\d+x\d+', '', url)
        url = re.sub(r'/\d+x\d+/', '/original/', url)
        url = re.sub(r'thumb_\d+', 'original', url)
        url = re.sub(r'small_\d+', 'original', url)
        url = re.sub(r'medium_\d+', 'original', url)
        url = re.sub(r'w=\d+', 'w=2048', url)
        url = re.sub(r'h=\d+', 'h=2048', url)
        url = re.sub(r'width=\d+', 'width=2048', url)
        url = re.sub(r'height=\d+', 'height=2048', url)
        url = re.sub(r'q=\d+', 'q=100', url)
        url = re.sub(r'quality=\d+', 'quality=100', url)
    except Exception as e:
        print(f"Помилка максимізації URL: {e}")

    return url


def _clean_and_deduplicate_urls(photo_urls):
    """Очищує та видаляє дублікати"""
    clean_urls = []
    seen_ids = set()

    for url in photo_urls:
        try:
            if not url or not isinstance(url, str) or not url.startswith('http'):
                continue

            url_lower = url.lower()
            if any(keyword in url_lower for keyword in ['logo', 'icon', 'avatar', 'banner', 'btn', 'button']):
                continue

            if not re.search(r'\.(jpg|jpeg|png|webp)', url, re.IGNORECASE):
                continue

            photo_id = _get_photo_id(url)
            if not photo_id or photo_id in seen_ids:
                continue

            seen_ids.add(photo_id)
            url = _maximize_image_size(url)
            clean_urls.append(url)

        except Exception as e:
            print(f"Помилка обробки URL {url}: {e}")
            continue

    return clean_urls


def is_lun_url(url):
    """Перевіряє чи є URL посиланням на LUN.ua"""
    if not url or not isinstance(url, str):
        return False
    return bool(re.match(r'https?://(?:www\.)?lun\.ua/', url))