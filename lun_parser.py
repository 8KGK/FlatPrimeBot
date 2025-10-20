"""
Модуль для парсингу фотографій з LUN.ua (Playwright версія)
"""

import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


async def download_lun_photos(url):
    """
    Асинхронна функція для завантаження фото з LUN.ua
    Використовується в async контексті (Telegram bot)
    """
    try:
        async with async_playwright() as p:
            # Запускаємо браузер в headless режимі
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )

            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()

            # Відкриваємо сторінку (domcontentloaded швидше ніж networkidle)
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            except Exception as e:
                print(f"Помилка завантаження сторінки: {e}")
                await browser.close()
                return []

            # Чекаємо завантаження галереї
            try:
                await page.wait_for_selector('div.lazyload-wrapper.NativeGallery_slide__KsrqV', timeout=15000)
                # Додатково чекаємо щоб JS точно виконався
                await page.wait_for_timeout(2000)
            except PlaywrightTimeout:
                print("Галерею не знайдено на сторінці")
                await browser.close()
                return []

            photo_urls = set()
            photo_hashes = set()  # Для перевірки унікальності по шляху файлу

            # Збираємо фото, прокручуючи галерею
            max_clicks = 100  # Максимум кліків по стрілці (захист від зациклення)
            clicks_count = 0
            no_new_photos_count = 0

            while clicks_count < max_clicks:
                # Збираємо поточні фото
                try:
                    slides = await page.query_selector_all('div.lazyload-wrapper.NativeGallery_slide__KsrqV')
                except Exception as e:
                    print(f"Помилка при пошуку слайдів: {e}")
                    break

                previous_count = len(photo_hashes)

                for slide in slides:
                    try:
                        # Шукаємо source теги з srcset
                        sources = await slide.query_selector_all('source')
                        for source in sources:
                            srcset = await source.get_attribute('srcset')
                            if srcset:
                                # Витягуємо URL (srcset може містити кілька URL)
                                urls = _parse_srcset(srcset)
                                for url in urls:
                                    # Отримуємо унікальний ідентифікатор фото (шлях без параметрів)
                                    photo_id = _get_photo_id(url)
                                    if photo_id and photo_id not in photo_hashes:
                                        photo_hashes.add(photo_id)
                                        photo_urls.add(url)

                        # Також перевіряємо img теги
                        imgs = await slide.query_selector_all('img')
                        for img in imgs:
                            src = await img.get_attribute('src') or await img.get_attribute('data-src')
                            if src and src.startswith('http'):
                                photo_id = _get_photo_id(src)
                                if photo_id and photo_id not in photo_hashes:
                                    photo_hashes.add(photo_id)
                                    photo_urls.add(src)
                    except Exception as e:
                        print(f"Помилка при обробці слайду: {e}")
                        continue

                # Перевіряємо чи з'явились нові фото
                if len(photo_hashes) == previous_count:
                    no_new_photos_count += 1
                    if no_new_photos_count >= 1:  # Тільки 1 спроба
                        print(f"Завершено: не знайдено нових фото")
                        break
                else:
                    no_new_photos_count = 0

                # Натискаємо на стрілку вправо
                try:
                    arrow = await page.query_selector('div.NavigationArrowRefresh-module_content__OTwEb')
                    if arrow and await arrow.is_visible():
                        await arrow.click()
                        # Чекаємо трохи для підгрузки
                        await page.wait_for_timeout(800)
                        clicks_count += 1
                    else:
                        # Стрілки немає або не видима - всі фото зібрані
                        print("Стрілка вправо не знайдена або не видима")
                        break
                except Exception as e:
                    print(f"Помилка при кліку на стрілку: {e}")
                    break

            await browser.close()

            # Очищаємо та максимізуємо якість
            clean_urls = _clean_and_deduplicate_urls(list(photo_urls))

            print(f"Знайдено {len(clean_urls)} унікальних фотографій")
            return clean_urls[:50]  # Максимум 50 фото

    except Exception as e:
        print(f"Критична помилка завантаження LUN.ua: {e}")
        import traceback
        traceback.print_exc()
        return []


def _parse_srcset(srcset):
    """
    Парсить srcset атрибут та витягує URL-и
    """
    urls = []
    if not srcset:
        return urls

    try:
        # srcset формат: "url1 1x, url2 2x" або "url1 400w, url2 800w"
        parts = srcset.split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Витягуємо URL (все до першого пробілу)
            url_parts = part.split()
            if url_parts and url_parts[0].startswith('http'):
                urls.append(url_parts[0])
    except Exception as e:
        print(f"Помилка парсингу srcset: {e}")

    return urls


def _get_photo_id(url):
    """
    Отримує унікальний ідентифікатор фото з URL
    Видаляє параметри, розміри, розширення
    """
    if not url:
        return None

    try:
        # Видаляємо параметри запиту
        url_base = url.split('?')[0]

        # Видаляємо розширення
        url_no_ext = re.sub(r'\.(jpg|jpeg|png|webp)$', '', url_base, flags=re.IGNORECASE)

        # Видаляємо параметри розміру з шляху
        url_no_ext = re.sub(r'_\d+x\d+$', '', url_no_ext)
        url_no_ext = re.sub(r'/\d+x\d+$', '', url_no_ext)
        url_no_ext = re.sub(r'_w\d+$', '', url_no_ext)
        url_no_ext = re.sub(r'_h\d+$', '', url_no_ext)

        return url_no_ext
    except Exception as e:
        print(f"Помилка отримання photo_id: {e}")
        return None


def _maximize_image_size(url):
    """
    Змінює URL зображення для отримання максимального розміру
    """
    if not url:
        return url

    try:
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
    except Exception as e:
        print(f"Помилка максимізації URL: {e}")

    return url


def _clean_and_deduplicate_urls(photo_urls):
    """
    Очищає, максимізує якість та видаляє дублікати з URL-ів
    """
    clean_urls = []
    seen_ids = set()

    for url in photo_urls:
        try:
            if not url or not isinstance(url, str) or not url.startswith('http'):
                continue

            # Ігноруємо іконки, логотипи та маленькі зображення
            url_lower = url.lower()
            if any(keyword in url_lower for keyword in ['logo', 'icon', 'avatar', 'banner', 'btn', 'button', 'thumb']):
                continue

            # Перевіряємо розширення файлу
            if not re.search(r'\.(jpg|jpeg|png|webp)', url, re.IGNORECASE):
                continue

            # Отримуємо ID фото
            photo_id = _get_photo_id(url)
            if not photo_id or photo_id in seen_ids:
                continue

            seen_ids.add(photo_id)

            # Максимізуємо розмір
            url = _maximize_image_size(url)
            clean_urls.append(url)

        except Exception as e:
            print(f"Помилка обробки URL {url}: {e}")
            continue

    return clean_urls


def is_lun_url(url):
    """
    Перевіряє чи є URL посиланням на LUN.ua
    """
    if not url or not isinstance(url, str):
        return False
    return bool(re.match(r'https?://(?:www\.)?lun\.ua/', url))


# Додаткова async версія для явного використання
async def download_lun_photos_async(url):
    """
    Експортована async версія (аліас)
    """
    return await download_lun_photos(url)