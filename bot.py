"""
Головний файл Telegram бота
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from io import BytesIO
import re
import zipfile
import os
from datetime import datetime

from image_processor import process_single_image
from olx_parser import download_olx_photos, parse_olx_parameters
from rieltor_parser import download_rieltor_photos, is_rieltor_url, parse_rieltor_parameters
from lun_parser import download_lun_photos, is_lun_url
from config import BOT_TOKEN
from database import get_all_users, verify_password, get_user_name, create_sessions_table
from auth import (
    is_authorized, authorize_user, logout_user,
    get_authorized_user, set_pending_auth,
    get_pending_auth, clear_pending_auth, init_sessions
)
from house_search import (
    search_house,
    format_house_info,
    get_total_houses_count
)
from house_parser import parse_all_districts, create_houses_table
from user_settings import (
    create_user_settings_table,
    get_watermark_position,
    set_watermark_position,
    get_position_name,
    WATERMARK_POSITIONS
)

# Telegram username адміністратора для оновлення бази будинків
ADMIN_USERNAME = "r24npo9"

# Час очікування між фото (в секундах)
PHOTO_BATCH_TIMEOUT = 3

# Райони Києва для inline клавіатури
KYIV_DISTRICTS = [
    'Голосіївський', 'Дарницький', 'Деснянський', 'Дніпровський',
    'Оболонський', 'Печерський', 'Подільський', 'Святошинський',
    'Солом\'янський', 'Шевченківський'
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    telegram_user_id = update.effective_user.id

    # Якщо вже авторизований - показуємо меню
    if is_authorized(telegram_user_id):
        await show_main_menu(update, context)
        return

    # Отримуємо список користувачів з БД
    users = get_all_users()

    if not users:
        await update.message.reply_text(
            "❌ Немає доступних користувачів у базі даних."
        )
        return

    # Створюємо клавіатуру з іменами
    keyboard = []
    for user_id, name in users:
        keyboard.append([KeyboardButton(name)])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "👋 Вітаю!\n\n"
        "Виберіть ваше ім'я зі списку:",
        reply_markup=reply_markup
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує головне меню з функціями бота"""
    user_data = get_authorized_user(update.effective_user.id)

    # Створюємо клавіатуру з функціями
    keyboard = [
        [KeyboardButton("📸 Фото"), KeyboardButton("🔗 OLX")],
        [KeyboardButton("🏠 Інфо про будинок"), KeyboardButton("⚙️ Налаштування")],
        [KeyboardButton("🚪 Вийти")]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f"✅ Вітаю, {user_data['name']}!\n\n"
        "Оберіть дію:\n\n"
        "📸 Фото - надішліть фото для обробки\n"
        "🔗 OLX - надішліть посилання на оголошення\n"
        "🏠 Інфо про будинок - інформація про будинки Києва\n"
        "⚙️ Налаштування - налаштування бота\n"
        "🚪 Вийти - вийти з аккаунту",
        reply_markup=reply_markup
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє текстові повідомлення"""
    telegram_user_id = update.effective_user.id
    text = update.message.text.strip()

    # Перевірка чи користувач очікує введення паролю
    pending_user_id = get_pending_auth(telegram_user_id)
    if pending_user_id:
        await handle_password(update, context, pending_user_id, text)
        return

    # Перевірка чи користувач шукає будинок
    if context.user_data.get('searching_house'):
        await handle_house_search(update, context, text)
        return

    # Перевірка авторизації
    if not is_authorized(telegram_user_id):
        await handle_name_selection(update, context, text)
        return

    # Обробка команд головного меню
    if text == "📸 Фото":
        await update.message.reply_text(
            "📸 Надішліть фотографії, і я їх обробляю:\n"
            "• Змінію розмір до мінімум 600x600\n"
            "• Додам водяний знак\n\n"
            "💡 Якщо надішлете більше 2 фото - отримаєте ZIP архів"
        )
    elif text == "🔗 OLX":
        await update.message.reply_text(
            "🔗 Надішліть посилання на оголошення\n\n"
            "Підтримуються сайти:\n"
            "• OLX\n"
            "• Rieltor.ua\n"
            "• LUN.ua"
        )
    elif text == "🏠 Інфо про будинок":
        await show_house_info_menu(update, context)
    elif text == "⚙️ Налаштування":
        await show_settings_menu(update, context)
    elif text == "🚪 Вийти":
        logout_user(telegram_user_id)
        await update.message.reply_text(
            "👋 До побачення!",
            reply_markup=ReplyKeyboardRemove()
        )
        await start(update, context)
    elif text.startswith('http'):
        # Обробка посилання на OLX
        await process_olx_url(update, context)
    else:
        await update.message.reply_text(
            "❓ Не розумію. Використовуйте кнопки меню або надішліть:\n"
            "📸 Фотографію для обробки\n"
            "🔗 Посилання на OLX"
        )


async def handle_name_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, selected_name: str):
    """Обробляє вибір імені користувача"""
    telegram_user_id = update.effective_user.id

    # Шукаємо користувача в БД за ім'ям
    users = get_all_users()
    user_id = None

    for db_user_id, name in users:
        if name == selected_name:
            user_id = db_user_id
            break

    if user_id:
        # Встановлюємо стан очікування паролю
        set_pending_auth(telegram_user_id, user_id)
        await update.message.reply_text(
            f"👤 {selected_name}\n\n"
            "🔐 Введіть пароль:",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await update.message.reply_text(
            "❌ Користувача не знайдено. Спробуйте ще раз.",
            reply_markup=ReplyKeyboardRemove()
        )
        await start(update, context)


async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, password: str):
    """Обробляє введення паролю"""
    telegram_user_id = update.effective_user.id


    if verify_password(user_id, password):

        user_name = get_user_name(user_id)
        authorize_user(telegram_user_id, user_id, user_name)

        await update.message.reply_text("✅ Авторизація успішна!")
        await show_main_menu(update, context)
    else:

        clear_pending_auth(telegram_user_id)
        await update.message.reply_text(
            "❌ Неправильний пароль!\n\n"
            "Спробуйте ще раз:",
            reply_markup=ReplyKeyboardRemove()
        )
        await start(update, context)


async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує меню налаштувань"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    telegram_user_id = update.effective_user.id

    # Отримуємо поточну позицію водяного знака
    current_position = get_watermark_position(telegram_user_id)
    current_position_name = get_position_name(current_position)

    # Створюємо inline клавіатуру з позиціями
    keyboard = []

    for position_key, position_name in WATERMARK_POSITIONS.items():
        # Додаємо галочку до поточної позиції
        button_text = f"✅ {position_name}" if position_key == current_position else position_name
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"set_wm_{position_key}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚙️ Налаштування\n\n"
        "📍 Де розміщувати водяний знак?\n\n"
        f"Поточна позиція: {current_position_name}",
        reply_markup=reply_markup
    )


async def handle_watermark_position_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє зміну позиції водяного знака"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    query = update.callback_query
    await query.answer()

    telegram_user_id = update.effective_user.id

    # Отримуємо нову позицію з callback_data
    position = query.data.replace("set_wm_", "")

    # Зберігаємо нову позицію
    if set_watermark_position(telegram_user_id, position):
        position_name = get_position_name(position)

        # Оновлюємо клавіатуру
        keyboard = []
        for position_key, pos_name in WATERMARK_POSITIONS.items():
            button_text = f"✅ {pos_name}" if position_key == position else pos_name
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"set_wm_{position_key}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "⚙️ Налаштування\n\n"
            "📍 Де розміщувати водяний знак?\n\n"
            f"Поточна позиція: {position_name}\n\n"
            "✅ Налаштування збережено!",
            reply_markup=reply_markup
        )
    else:
        await query.answer("❌ Помилка збереження налаштувань", show_alert=True)


async def process_photo_batch(context: ContextTypes.DEFAULT_TYPE):
    """Обробляє пакет фото після закінчення таймауту"""
    job_data = context.job.data
    telegram_user_id = job_data['user_id']
    chat_id = job_data['chat_id']

    # Отримуємо фото з context.user_data
    photos = context.application.bot_data.get(f'photos_{telegram_user_id}', [])

    if not photos:
        return

    try:
        photo_count = len(photos)

        if photo_count <= 2:
            # Відправляємо фото окремо
            for i, photo_data in enumerate(photos, 1):
                output = BytesIO()
                photo_data['image'].save(output, format='JPEG', quality=95)
                output.seek(0)

                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=output,
                    caption=f"✅ Фото {i}/{photo_count} оброблено!"
                )
        else:
            # Створюємо ZIP архів
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📦 Створюю архів з {photo_count} фото..."
            )

            zip_buffer = BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for i, photo_data in enumerate(photos, 1):
                    img_buffer = BytesIO()
                    photo_data['image'].save(img_buffer, format='JPEG', quality=95)
                    img_buffer.seek(0)

                    filename = f"photo_{i:02d}.jpg"
                    zip_file.writestr(filename, img_buffer.getvalue())

            zip_buffer.seek(0)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photos_{timestamp}.zip"

            await context.bot.send_document(
                chat_id=chat_id,
                document=zip_buffer,
                filename=filename,
                caption=f"✅ Готово! Оброблено {photo_count} фото"
            )

    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Помилка при обробці фото: {str(e)}"
        )
    finally:
        # Очищуємо дані про фото
        if f'photos_{telegram_user_id}' in context.application.bot_data:
            del context.application.bot_data[f'photos_{telegram_user_id}']


async def process_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_user_id = update.effective_user.id

    # Перевірка авторизації
    if not is_authorized(telegram_user_id):
        await update.message.reply_text(
            "❌ Спочатку авторизуйтесь!\n"
            "Натисніть /start"
        )
        return

    try:
        # Завантажуємо фото
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()

        from PIL import Image
        image = Image.open(BytesIO(photo_bytes))

        # Отримуємо позицію водяного знака для користувача
        watermark_position = get_watermark_position(telegram_user_id)

        # Обробляємо фото з вказаною позицією
        processed_image = process_single_image(image, watermark_position)

        if not processed_image:
            await update.message.reply_text("❌ Помилка при обробці фото")
            return

        # Ініціалізуємо список фото для користувача, якщо його немає
        if f'photos_{telegram_user_id}' not in context.application.bot_data:
            context.application.bot_data[f'photos_{telegram_user_id}'] = []

        # Додаємо оброблене фото до списку
        context.application.bot_data[f'photos_{telegram_user_id}'].append({
            'image': processed_image,
            'timestamp': datetime.now()
        })

        photo_count = len(context.application.bot_data[f'photos_{telegram_user_id}'])

        # Скасовуємо попередній таймер, якщо він є
        current_jobs = context.job_queue.get_jobs_by_name(f'photo_batch_{telegram_user_id}')
        for job in current_jobs:
            job.schedule_removal()

        # Створюємо новий таймер
        context.job_queue.run_once(
            process_photo_batch,
            PHOTO_BATCH_TIMEOUT,
            data={
                'user_id': telegram_user_id,
                'chat_id': update.effective_chat.id
            },
            name=f'photo_batch_{telegram_user_id}'
        )

        # Відправляємо підтвердження
        await update.message.reply_text(
            f"📸 Фото {photo_count} отримано\n"
            f"⏳ Чекаю ще {PHOTO_BATCH_TIMEOUT} сек..."
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


def format_parameters(parameters, site_name):
    """
    Форматує параметри для відображення
    """
    if not parameters:
        return ""

    lines = [f"\n📋 Інформація про квартиру ({site_name}):\n"]


    param_order = [
        'Кількість кімнат',
        'Загальна площа',
        'Житлова площа',
        'Площа кухні',
        'Поверх',
        'Поверховість',
        'Тип будинку',
        'Тип стін',
        'Ремонт',
        'Меблювання'
    ]

    for param_name in param_order:
        if param_name in parameters:

            emoji = {
                'Кількість кімнат': '🚪',
                'Загальна площа': '📐',
                'Житлова площа': '🏠',
                'Площа кухні': '🍳',
                'Поверх': '🔼',
                'Поверховість': '🏢',
                'Тип будинку': '🏗',
                'Тип стін': '🧱',
                'Ремонт': '🔨',
                'Меблювання': '🛋'
            }.get(param_name, '▪️')

            lines.append(f"{emoji} {param_name}: {parameters[param_name]}")

    return '\n'.join(lines)


async def process_olx_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє посилання на OLX, Rieltor.ua або LUN.ua та відправляє архів з фото"""
    telegram_user_id = update.effective_user.id

    # Перевірка авторизації
    if not is_authorized(telegram_user_id):
        await update.message.reply_text(
            "❌ Спочатку авторизуйтесь!\n"
            "Натисніть /start"
        )
        return

    url = update.message.text.strip()

    parameters = {}

    if re.match(r'https?://(?:www\.)?olx\.ua/', url):
        site_name = "OLX"
        await update.message.reply_text("🔍 Завантажую інформацію з OLX...")
        photo_urls = download_olx_photos(url)
        parameters = parse_olx_parameters(url)
    elif is_rieltor_url(url):
        site_name = "Rieltor.ua"
        await update.message.reply_text("🔍 Завантажую інформацію з Rieltor.ua...")
        photo_urls = download_rieltor_photos(url)
        parameters = parse_rieltor_parameters(url)
    elif is_lun_url(url):
        site_name = "LUN.ua"
        await update.message.reply_text("🔍 Завантажую фотографії з LUN.ua...")
        photo_urls = await download_lun_photos(url)  # ← ДОДАНО await

    else:
        await update.message.reply_text(
            "❌ Посилання не розпізнано\n\n"
            "Підтримуються сайти:\n"
            "• OLX: https://www.olx.ua/d/uk/obyavlenie/...\n"
            "• Rieltor.ua: https://rieltor.ua/flats-sale/view/...\n"
            "• LUN.ua: https://lun.ua/realty/..."
        )
        return

    try:
        if not photo_urls:
            await update.message.reply_text(
                "❌ Не вдалося знайти фотографії в оголошенні.\n"
                "Можливо, оголошення приватне або видалене."
            )
            return

        if parameters:
            params_text = format_parameters(parameters, site_name)
            await update.message.reply_text(params_text, parse_mode='Markdown')

        progress_message = await update.message.reply_text(
            f"📸 Знайдено {len(photo_urls)} фото.\n⏳ Обробляю: 0/{len(photo_urls)}"
        )

        zip_buffer = BytesIO()

        processed_count = 0
        import requests
        from PIL import Image

        # Отримуємо позицію водяного знака для користувача
        watermark_position = get_watermark_position(telegram_user_id)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, photo_url in enumerate(photo_urls, 1):
                try:
                    # Завантажуємо фото
                    response = requests.get(photo_url, headers=headers, timeout=10)
                    response.raise_for_status()

                    # Відкриваємо зображення
                    image = Image.open(BytesIO(response.content))

                    # Обробляємо фото з позицією водяного знака користувача
                    processed_image = process_single_image(image, watermark_position)

                    if processed_image:
                        # Зберігаємо в буфер
                        img_buffer = BytesIO()
                        processed_image.save(img_buffer, format='JPEG', quality=95)
                        img_buffer.seek(0)

                        # Додаємо в архів
                        filename = f"photo_{i:02d}.jpg"
                        zip_file.writestr(filename, img_buffer.getvalue())

                        processed_count += 1

                        # Оновлюємо повідомлення про прогрес кожні 3 фото
                        if processed_count % 3 == 0 or processed_count == len(photo_urls):
                            try:
                                await progress_message.edit_text(
                                    f"📸 Знайдено {len(photo_urls)} фото.\n⏳ Оброблено: {processed_count}/{len(photo_urls)}"
                                )
                            except:
                                pass

                except Exception as e:
                    print(f"Помилка обробки фото {i}: {e}")
                    continue

        if processed_count > 0:
            # Повертаємось на початок буфера
            zip_buffer.seek(0)

            # Генеруємо ім'я файлу з датою та часом
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{site_name.lower().replace('.', '_')}_photos_{timestamp}.zip"

            # Відправляємо архів без повторення параметрів
            caption = f"🎉 Готово! Оброблено {processed_count} з {len(photo_urls)} фото"

            # Відправляємо архів
            await update.message.reply_document(
                document=zip_buffer,
                filename=filename,
                caption=caption
            )
        else:
            await update.message.reply_text("❌ Не вдалося обробити жодного фото")

    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def show_house_info_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує меню для пошуку інформації про будинки"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    # Отримуємо кількість будинків в базі
    total_count = get_total_houses_count()

    if total_count == 0:
        await update.message.reply_text(
            "❌ База даних будинків порожня.\n"
            "Адміністратор має оновити базу командою /update_houses"
        )
        return

    # Створюємо inline клавіатуру з районами (по 2 в ряд)
    keyboard = []
    for i in range(0, len(KYIV_DISTRICTS), 2):
        row = []
        for district in KYIV_DISTRICTS[i:i + 2]:
            row.append(InlineKeyboardButton(district, callback_data=f"district_{district}"))
        keyboard.append(row)

    # Додаємо кнопку прямого пошуку
    keyboard.append([InlineKeyboardButton("🔍 Пошук за адресою", callback_data="direct_search")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🏠 База будинків Києва\n\n"
        f"📊 Всього будинків: {total_count}\n\n"
        f"Оберіть район або введіть адресу:",
        reply_markup=reply_markup
    )


async def handle_district_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє вибір району"""
    query = update.callback_query
    await query.answer()

    district = query.data.replace("district_", "")

    # Зберігаємо вибраний район
    context.user_data['selected_district'] = district
    context.user_data['searching_house'] = True

    await query.edit_message_text(
        f"📍 Район: {district}\n\n"
        f"Введіть адресу будинку:\n\n"
        f"Приклади:\n"
        f"• Хрещатик 15\n"
        f"• вул. Велика Васильківська, 1\n"
        f"• Червоноармійська 112",
        parse_mode='Markdown'
    )


async def handle_direct_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє прямий пошук за адресою"""
    query = update.callback_query
    await query.answer()

    context.user_data['selected_district'] = None
    context.user_data['searching_house'] = True

    await query.edit_message_text(
        "🔍 Пошук за адресою\n\n"
        "Введіть адресу будинку:\n\n"
        "Приклади:\n"
        "• Хрещатик 15\n"
        "• вул. Велика Васильківська, 1\n"
        "• Червоноармійська 112",
        parse_mode='Markdown'
    )


async def handle_house_search(update: Update, context: ContextTypes.DEFAULT_TYPE, address: str):
    """Обробляє пошук будинку за адресою"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    # Очищаємо стан пошуку
    context.user_data['searching_house'] = False

    await update.message.reply_text("🔍 Шукаю...")

    # Шукаємо будинок
    results = search_house(address)

    if not results:
        keyboard = [[InlineKeyboardButton("🔄 Спробувати ще раз", callback_data="direct_search")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"❌ Не знайдено будинків за адресою:\n{address}\n\n"
            f"Спробуйте інший формат:\n"
            f"• Хрещатик 15\n"
            f"• Велика Васильківська 1",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    # Показуємо перший результат
    house_info = format_house_info(results[0])

    # Якщо знайдено більше 1 будинку - додаємо кнопку "Показати всі"
    if len(results) > 1:
        # Зберігаємо результати для показу всіх
        context.user_data['search_results'] = results

        keyboard = [
            [InlineKeyboardButton(f"📋 Показати всі ({len(results)})", callback_data="show_all_results")],
            [InlineKeyboardButton("🔍 Новий пошук", callback_data="direct_search")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"{house_info}\n\n"
            f"ℹ️ Знайдено ще {len(results) - 1} будинків за цією адресою",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        keyboard = [[InlineKeyboardButton("🔍 Новий пошук", callback_data="direct_search")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            house_info,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def handle_show_all_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує всі знайдені результати"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    query = update.callback_query
    await query.answer()

    results = context.user_data.get('search_results', [])

    if not results:
        await query.edit_message_text("❌ Результати пошуку не знайдено")
        return

    # Формуємо повідомлення з усіма результатами
    messages = []
    current_message = f"📋 Знайдено будинків: {len(results)}\n\n"

    for i, house in enumerate(results, 1):
        house_text = f"{i}. {house['address']}, {house['house_number']}\n"
        house_text += f"   📍 {house['region']}\n"

        if house.get('project'):
            house_text += f"   🏗 {house['project']}"
        if house.get('build_year'):
            house_text += f" ({house['build_year']})"
        house_text += "\n\n"

        # Перевіряємо чи не перевищуємо ліміт символів
        if len(current_message + house_text) > 4000:
            messages.append(current_message)
            current_message = house_text
        else:
            current_message += house_text

    if current_message:
        messages.append(current_message)

    # Відправляємо перше повідомлення (замінює попереднє)
    keyboard = [[InlineKeyboardButton("🔍 Новий пошук", callback_data="direct_search")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        messages[0],
        parse_mode='Markdown',
        reply_markup=reply_markup if len(messages) == 1 else None
    )

    # Якщо є ще повідомлення - відправляємо їх окремо
    for message in messages[1:]:
        await query.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup if message == messages[-1] else None
        )


async def update_houses_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Оновлює базу даних будинків (тільки для адміністратора)
    """
    telegram_user_id = update.effective_user.id
    username = update.effective_user.username

    # Перевірка прав адміністратора
    if username != ADMIN_USERNAME:
        await update.message.reply_text(
            "❌ У вас немає прав для виконання цієї команди"
        )
        return

    progress_msg = await update.message.reply_text(
        "🚀 Починаю оновлення бази даних будинків...\n"
        "⏳ Це може зайняти 5-10 хвилин"
    )

    # Створюємо таблицю якщо не існує
    create_houses_table()

    # Словник для передачі прогресу між потоками
    progress_data = {
        'district': '',
        'page': 0,
        'total': 0,
        'found': 0
    }

    # Запускаємо парсинг в окремому потоці
    import asyncio
    import threading

    result = {'total': 0, 'error': None}

    def run_parser():
        try:
            result['total'] = parse_all_districts(progress_data)
        except Exception as e:
            result['error'] = str(e)

    # Запускаємо парсинг в окремому потоці
    parser_thread = threading.Thread(target=run_parser)
    parser_thread.start()

    # Оновлюємо прогрес кожні 3 секунди
    last_update = ""
    while parser_thread.is_alive():
        current_update = (
            f"📍 {progress_data['district']}\n"
            f"📄 Сторінка: {progress_data['page']}/{progress_data['total']}\n"
            f"🏠 Знайдено на сторінці: {progress_data['found']}"
        )

        # Оновлюємо тільки якщо є зміни
        if current_update != last_update and progress_data['district']:
            try:
                await progress_msg.edit_text(current_update, parse_mode='Markdown')
                last_update = current_update
            except:
                pass

        await asyncio.sleep(3)

    # Чекаємо завершення потоку
    parser_thread.join()

    # Перевіряємо результат
    if result['error']:
        await update.message.reply_text(
            f"❌ Помилка при оновленні бази:\n{result['error']}"
        )
    else:
        await update.message.reply_text(
            f"✅ Оновлення завершено!\n\n"
            f"📊 Всього додано будинків: {result['total']}",
            parse_mode='Markdown'
        )


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє callback запити від inline кнопок"""
    query = update.callback_query

    if query.data.startswith("district_"):
        await handle_district_selection(update, context)
    elif query.data == "direct_search":
        await handle_direct_search(update, context)
    elif query.data == "show_all_results":
        await handle_show_all_results(update, context)
    elif query.data.startswith("set_wm_"):
        await handle_watermark_position_change(update, context)


def main():
    """Запускає бота"""
    # Створюємо таблицю сесій якщо не існує
    create_sessions_table()

    # Створюємо таблицю будинків якщо не існує
    create_houses_table()

    # Створюємо таблицю налаштувань користувачів
    create_user_settings_table()

    # Завантажуємо активні сесії з БД
    init_sessions()

    # Створюємо додаток
    application = Application.builder().token(BOT_TOKEN).build()

    # Додаємо обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update_houses", update_houses_database))

    # Додаємо обробники повідомлень
    application.add_handler(MessageHandler(filters.PHOTO, process_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Додаємо обробник callback запитів
    from telegram.ext import CallbackQueryHandler
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    # Запускаємо бота
    print("🤖 Бот запущено!")
    print("📝 Система авторизації активна")
    print("🔐 Підключено до бази даних MySQL")
    print("💾 Сесії зберігаються в БД")
    print("📦 Фото з OLX, Rieltor.ua та LUN.ua відправляються ZIP архівом")
    print("📋 Парсинг параметрів квартир активний")
    print("🏠 База даних будинків Києва активна")
    print("📸 Пакетна обробка фото активна (>3 фото = ZIP архів)")
    print("⚙️ Персональні налаштування водяного знака активні")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()