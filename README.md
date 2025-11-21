# FlatPrimeBot 🏙️🤖

Telegram-бот для автоматизации подбора недвижимости для агентства **FlatPrime**.  
Бот парсит популярные сайты с объявлениями (OLX, LUN, Rieltor.ua и др.), сохраняет объекты в базу и помогает быстро подбирать варианты под запрос клиента.  

[//]: # (Badges)
![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![Telegram Bot](https://img.shields.io/badge/Telegram%20Bot-active-26A5E4.svg)
![Docker](https://img.shields.io/badge/Docker-ready-0db7ed.svg)

---

## ✨ Основные возможности

- 🔍 **Поиск объектов** по ключевым параметрам (район, цена, количество комнат и т.д.).
- 🌐 **Парсинг площадок**:
  - OLX  
  - Rieltor.ua  
- 💾 **Сохранение базы объявлений** в SQL-базе (структура в `backup.sql`).
- ⚙️ **Гибкие пользовательские настройки** (фильтры, избранное, источники и т.п.).
- 🖼️ **Обработка изображений**:
  - наложение водяного знака агенции (см. `image_processor.py` и `watermark.png`);
- 🐳 **Запуск через Docker**:
  - `Dockerfile` + `docker-compose.yml` для быстрого деплоя.
- 🛡️ Разделение конфигурации и секретов через `config.py` / переменные окружения.

---

## 🧱 Технологии

- **Язык:** Python 3.x  
- **Интеграция:** Telegram Bot API  
- **База данных:** SQL (структура — `backup.sql`)  
- **Инфраструктура:** Docker, docker-compose  

---

## 📂 Структура проекта

Ключевые файлы и директории:

- `bot.py` — основной файл бота, точка входа.
- `config.py` — настройки проекта, токен бота, параметры БД и др.
- `database.py` — работа с базой данных.
- `user_settings.py` — хранение и обработка пользовательских настроек.
- `auth.py` — вспомогательная логика авторизации/доступа.
- `backup.sql` — дамп/структура базы данных.
- Парсеры:
  - `olx_parser.py`
  - `lun_parser.py`
  - `rieltor_parser.py`
  - `house_parser.py`
- Логика поиска:
  - `house_search.py`
  - `residential_complex.py`
- Работа с изображениями:
  - `image_processor.py`
  - `watermark.png`
- Docker/деплой:
  - `Dockerfile`
  - `docker-compose.yml`
- Прочее:
  - `requirements.txt` — зависимости проекта

