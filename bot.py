"""
Головний файл Telegram бота з авторизацією
Обробляє команди та повідомлення користувачів
"""

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from io import BytesIO
import re
import zipfile
import os
from datetime import datetime

from image_processor import process_single_image
from olx_parser import download_olx_photos
from rieltor_parser import download_rieltor_photos, is_rieltor_url
from lun_parser import download_lun_photos, is_lun_url
from config import BOT_TOKEN
from database import get_all_users, verify_password, get_user_name, create_sessions_table
from auth import (
    is_authorized, authorize_user, logout_user,
    get_authorized_user, set_pending_auth,
    get_pending_auth, clear_pending_auth, init_sessions
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відправляє список користувачів для вибору"""
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
        [KeyboardButton("🚪 Вийти")]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f"✅ Вітаю, {user_data['name']}!\n\n"
        "Оберіть дію:\n\n"
        "📸 **Фото** - надішліть фото для обробки\n"
        "🔗 **OLX** - надішліть посилання на оголошення\n"
        "🚪 **Вийти** - вийти з аккаунту",
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

    # Перевірка авторизації
    if not is_authorized(telegram_user_id):
        await handle_name_selection(update, context, text)
        return

    # Обробка команд головного меню
    if text == "📸 Фото":
        await update.message.reply_text(
            "📸 Надішліть фотографію, і я її обробляю:\n"
            "• Змінію розмір до мінімум 600x600\n"
            "• Додам водяний знак"
        )
    elif text == "🔗 OLX":
        await update.message.reply_text(
            "🔗 Надішліть посилання на оголошення\n\n"
            "Підтримуються сайти:\n"
            "• OLX\n"
            "• Rieltor.ua\n"
        )
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

    # Перевіряємо пароль
    if verify_password(user_id, password):
        # Пароль правильний - авторизуємо
        user_name = get_user_name(user_id)
        authorize_user(telegram_user_id, user_id, user_name)

        await update.message.reply_text("✅ Авторизація успішна!")
        await show_main_menu(update, context)
    else:
        # Пароль неправильний
        clear_pending_auth(telegram_user_id)
        await update.message.reply_text(
            "❌ Неправильний пароль!\n\n"
            "Спробуйте ще раз:",
            reply_markup=ReplyKeyboardRemove()
        )
        await start(update, context)


async def process_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє отримані фотографії"""
    telegram_user_id = update.effective_user.id

    # Перевірка авторизації
    if not is_authorized(telegram_user_id):
        await update.message.reply_text(
            "❌ Спочатку авторизуйтесь!\n"
            "Натисніть /start"
        )
        return

    try:
        # Отримуємо файл найвищої якості
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        # Завантажуємо фото
        photo_bytes = await file.download_as_bytearray()
        from PIL import Image
        image = Image.open(BytesIO(photo_bytes))

        # Обробляємо фото
        processed_image = process_single_image(image)

        if processed_image:
            # Зберігаємо результат
            output = BytesIO()
            processed_image.save(output, format='JPEG', quality=95)
            output.seek(0)

            # Відправляємо оброблене фото
            await update.message.reply_photo(
                photo=output,
                caption="✅ Фото оброблено!"
            )
        else:
            await update.message.reply_text("❌ Помилка при обробці фото")

    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


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

    # Визначаємо тип сайту та завантажуємо фото
    if re.match(r'https?://(?:www\.)?olx\.ua/', url):
        site_name = "OLX"
        await update.message.reply_text("🔍 Завантажую фотографії з OLX...")
        photo_urls = download_olx_photos(url)
    elif is_rieltor_url(url):
        site_name = "Rieltor.ua"
        await update.message.reply_text("🔍 Завантажую фотографії з Rieltor.ua...")
        photo_urls = download_rieltor_photos(url)
    elif is_lun_url(url):
        site_name = "LUN.ua"
        await update.message.reply_text("🔍 Завантажую фотографії з LUN.ua...")
        photo_urls = download_lun_photos(url)
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
        # Завантажуємо URL-и фотографій
        photo_urls = photo_urls  # Вже завантажені вище

        if not photo_urls:
            await update.message.reply_text(
                "❌ Не вдалося знайти фотографії в оголошенні.\n"
                "Можливо, оголошення приватне або видалене."
            )
            return

        # Відправляємо повідомлення про початок обробки
        progress_message = await update.message.reply_text(
            f"📸 Знайдено {len(photo_urls)} фото.\n⏳ Обробляю: 0/{len(photo_urls)}"
        )

        # Створюємо ZIP архів в пам'яті
        zip_buffer = BytesIO()

        processed_count = 0
        import requests
        from PIL import Image

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

                    # Обробляємо фото
                    processed_image = process_single_image(image)

                    if processed_image:
                        # Зберігаємо в буфер
                        img_buffer = BytesIO()
                        processed_image.save(img_buffer, format='JPEG', quality=95)
                        img_buffer.seek(0)

                        # Додаємо в архів
                        filename = f"photo_{i:02d}.jpg"
                        zip_file.writestr(filename, img_buffer.getvalue())

                        processed_count += 1

                        # Оновлюємо повідомлення про прогрес
                        try:
                            await progress_message.edit_text(
                                f"📸 Знайдено {len(photo_urls)} фото.\n⏳ Оброблено: {processed_count}/{len(photo_urls)}"
                            )
                        except:
                            pass  # Ігноруємо помилки редагування (наприклад, якщо текст не змінився)

                except Exception as e:
                    print(f"Помилка обробки фото {i}: {e}")
                    continue

        if processed_count > 0:
            # Повертаємось на початок буфера
            zip_buffer.seek(0)

            # Генеруємо ім'я файлу з датою та часом
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{site_name.lower().replace('.', '_')}_photos_{timestamp}.zip"

            # Відправляємо архів
            await update.message.reply_document(
                document=zip_buffer,
                filename=filename,
                caption=f"🎉 Готово! Оброблено {processed_count} з {len(photo_urls)} фото"
            )
        else:
            await update.message.reply_text("❌ Не вдалося обробити жодного фото")

    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


def main():
    """Запускає бота"""
    # Створюємо таблицю сесій якщо не існує
    create_sessions_table()

    # Завантажуємо активні сесії з БД
    init_sessions()

    # Створюємо додаток
    application = Application.builder().token(BOT_TOKEN).build()

    # Додаємо обробники
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, process_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Запускаємо бота
    print("🤖 Бот запущено!")
    print("📝 Система авторизації активна")
    print("🔐 Підключено до бази даних MySQL")
    print("💾 Сесії зберігаються в БД")
    print("📦 Фото з OLX, Rieltor.ua та LUN.ua відправляються ZIP архівом")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()