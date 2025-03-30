import os
import json
import base64
import logging
import asyncio
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters
from telegram.constants import ParseMode

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
TELEGRAM_BOT_TOKEN = "7639285272:AAH-vhuRyoVDMNjqyvkDgfsZw7_d5GEc77Q"
ADMIN_ID = 8199808170
ADMIN_USERNAME = "aunex"  # Имя пользователя администратора
ANTHROPIC_API_KEY = "sk-Rr88gyoBb4RD9ipDp4vHqXa9W0CkA8piOCN8swUfvqsCiuOf2j5Eg-aNqRwgUKyHw6n2qvtlIb1uSV385QUfpA"
ANTHROPIC_API_URL = "https://api.langdock.com/anthropic/eu/v1/messages"
MAX_MEMORY_MESSAGES = 20  # Увеличено до 20 сообщений
MAX_MESSAGE_LENGTH = 4000  # Максимальная длина сообщения в Telegram

# Хранение данных пользователей
users_data = {}
# Память для хранения истории сообщений пользователей
user_memory = {}

# Константы для клавиатур
USER_KEYBOARD_COMMANDS = ["🔄 Сбросить историю", "ℹ️ Помощь"]

# Создание клавиатуры для пользователя
def get_user_keyboard():
    keyboard = [USER_KEYBOARD_COMMANDS]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Загрузка данных пользователей из файла, если он существует
def load_users_data():
    global users_data
    try:
        if os.path.exists('users_data.json'):
            with open('users_data.json', 'r', encoding='utf-8') as file:
                users_data = json.load(file)
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных пользователей: {e}")
        users_data = {}

# Сохранение данных пользователей в файл
def save_users_data():
    try:
        with open('users_data.json', 'w', encoding='utf-8') as file:
            json.dump(users_data, file, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных пользователей: {e}")

# Инициализация нового пользователя
def init_user(user_id):
    if str(user_id) not in users_data:
        users_data[str(user_id)] = {
            "unlimited": True,  # Все пользователи имеют безлимит
            "name": "",
            "username": "",
        }
        save_users_data()

# Инициализация памяти пользователя
def init_user_memory(user_id):
    if user_id not in user_memory:
        user_memory[user_id] = []

# Отправка запроса к API Anthropic
async def query_anthropic(messages):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY
    }
    
    payload = {
        "model": "claude-3-7-sonnet-20250219",
        "messages": messages,
        "max_tokens": 4000
    }
    
    try:
        import requests
        response = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка запроса к Anthropic API: {e}")
        return {"error": str(e)}

# Функция для разбивки длинного текста на части
def split_text(text, max_length=MAX_MESSAGE_LENGTH):
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    sentences = text.split(". ")
    
    for sentence in sentences:
        if len(current_part) + len(sentence) + 2 <= max_length:
            if current_part:
                current_part += ". " + sentence
            else:
                current_part = sentence
        else:
            if current_part:
                parts.append(current_part + ".")
                current_part = sentence
            else:
                # Если одно предложение слишком длинное, разбиваем его по словам
                words = sentence.split(" ")
                current_part = ""
                for word in words:
                    if len(current_part) + len(word) + 1 <= max_length:
                        if current_part:
                            current_part += " " + word
                        else:
                            current_part = word
                    else:
                        parts.append(current_part)
                        current_part = word
                if current_part:
                    parts.append(current_part)
                current_part = ""
    
    if current_part:
        parts.append(current_part)
    
    return parts

# Отправка длинного сообщения частями
async def send_long_message(update, text, reply_markup=None):
    parts = split_text(text)
    # Добавляем нумерацию частей если частей больше одной
    if len(parts) > 1:
        for i, part in enumerate(parts):
            # Последняя часть получает клавиатуру
            if i == len(parts) - 1 and reply_markup:
                await update.message.reply_text(f"Часть {i+1}/{len(parts)}:\n\n{part}", reply_markup=reply_markup)
            else:
                await update.message.reply_text(f"Часть {i+1}/{len(parts)}:\n\n{part}")
            # Небольшая задержка между сообщениями чтобы избежать ограничений Telegram
            await asyncio.sleep(0.5)
    else:
        await update.message.reply_text(parts[0], reply_markup=reply_markup)

# Обработка команды /start
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = update.effective_user.username
    
    init_user(user_id)
    init_user_memory(user_id)
    
    # Обновляем имя и username пользователя
    users_data[str(user_id)]["name"] = user_name
    users_data[str(user_id)]["username"] = username or ""
    save_users_data()
    
    welcome_message = (
        "🌟 *Добро пожаловать в бот Claude 3.7 Sonnet!* 🌟\n\n"
        "Я - ваш персональный ИИ-ассистент на базе Claude 3.7 Sonnet от Anthropic. "
        "Я могу отвечать на вопросы, анализировать изображения и помогать с текстами.\n\n"
        "📱 *Основные функции:*\n"
        "• Ответы на любые вопросы\n"
        "• Анализ изображений\n"
        "• Помощь в написании текстов\n"
        "• Последние 20 сообщений сохраняются в памяти\n\n"
        "⌨️ *Доступные кнопки:*\n"
        "🔄 Сбросить историю - сбросить историю диалога\n"
        "ℹ️ Помощь - показать справку\n\n"
        "Просто начните общение, отправив сообщение или изображение! 🚀"
    )
    
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN, reply_markup=get_user_keyboard())

# Обработка команды "🔄 Сбросить историю"
async def reset_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    init_user_memory(user_id)
    user_memory[user_id] = []
    
    await update.message.reply_text("История диалога очищена! 🧹")

# Обработка команды "ℹ️ Помощь"
async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "🔍 *Справка по использованию бота:*\n\n"
        "📝 *Основные возможности:*\n"
        "• Задавайте любые вопросы\n"
        "• Отправляйте изображения для анализа\n"
        "• Получайте большие тексты разбитыми на удобные части\n"
        "• Бот помнит последние 20 сообщений диалога\n\n"
        "⚠️ *Ограничения:*\n"
        "• Видео, аудио, документы и другие типы файлов не поддерживаются и будут удалены\n\n"
        "⌨️ *Доступные кнопки:*\n"
        "🔄 Сбросить историю - очистить историю диалога\n"
        "ℹ️ Помощь - показать это сообщение\n\n"
        "💰 У вас безлимитный доступ к боту!\n"
    )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Обработка текстовых сообщений
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    init_user(user_id)
    init_user_memory(user_id)
    
    user_message = update.message.text
    
    # Обработка команд клавиатуры
    if user_message in USER_KEYBOARD_COMMANDS:
        if user_message == "🔄 Сбросить историю":
            await reset_command(update, context)
            return
        elif user_message == "ℹ️ Помощь":
            await help_command(update, context)
            return
    
    # Добавление сообщения пользователя в память
    user_memory[user_id].append({"role": "user", "content": user_message})
    
    # Ограничение памяти до последних MAX_MEMORY_MESSAGES сообщений
    if len(user_memory[user_id]) > MAX_MEMORY_MESSAGES:
        user_memory[user_id] = user_memory[user_id][-MAX_MEMORY_MESSAGES:]
    
    # Определяем, если это запрос на большой текст (реферат, эссе и т.д.)
    is_long_content_request = any(keyword in user_message.lower() for keyword in 
                               ["реферат", "эссе", "сочинение", "статья", "доклад", "текст на", 
                                "напиши большой", "3000 слов", "2000 слов", "много текста",
                                "развернутый ответ", "подробно опиши", "подробный анализ"])
    
    # Отправляем статус набора текста
    await update.message.chat.send_action("typing")
    
    # Отправка запроса к Anthropic
    response = await query_anthropic(user_memory[user_id])
    
    if "error" in response:
        await update.message.reply_text(f"Произошла ошибка: {response['error']}")
        return
    
    # Обработка ответа от API
    if "content" in response and len(response["content"]) > 0:
        assistant_response = response["content"][0]["text"]
        
        # Добавление ответа помощника в память
        user_memory[user_id].append({"role": "assistant", "content": assistant_response})
        
        # Отправка ответа пользователю: разбиваем на части если это большой ответ
        if is_long_content_request or len(assistant_response) > MAX_MESSAGE_LENGTH:
            await send_long_message(update, assistant_response, get_user_keyboard())
        else:
            await update.message.reply_text(assistant_response, reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text("Не удалось получить ответ от Claude. Попробуйте еще раз.", reply_markup=get_user_keyboard())

# Обработка фотографий
async def handle_photo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    init_user(user_id)
    init_user_memory(user_id)
    
    # Получение фотографии с наилучшим качеством
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    # Преобразование изображения в base64
    image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
    
    # Создаем сообщение с изображением
    caption = update.message.caption or "Опишите эту фотографию"
    
    # Определяем, если это запрос на большой текст
    is_long_content_request = any(keyword in caption.lower() for keyword in 
                               ["реферат", "эссе", "сочинение", "статья", "доклад", "текст на", 
                                "напиши большой", "3000 слов", "2000 слов", "много текста",
                                "развернутый ответ", "подробно опиши", "подробный анализ"])
    
    message_with_image = {
        "role": "user",
        "content": [
            {"type": "text", "text": caption},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}}
        ]
    }
    
    # Получаем историю диалога без изображений
    text_history = []
    for msg in user_memory[user_id]:
        if isinstance(msg["content"], str):
            text_history.append({"role": msg["role"], "content": msg["content"]})
    
    # Добавляем текущее сообщение с изображением
    messages_to_send = text_history + [message_with_image]
    
    # Отправка запроса к Anthropic
    await update.message.chat.send_action("typing")
    response = await query_anthropic(messages_to_send)
    
    if "error" in response:
        await update.message.reply_text(f"Произошла ошибка: {response['error']}")
        return
    
    # Обработка ответа от API
    if "content" in response and len(response["content"]) > 0:
        assistant_response = response["content"][0]["text"]
        
        # Добавление запроса пользователя и ответа помощника в память
        user_memory[user_id].append({"role": "user", "content": caption + " [фотография]"})
        user_memory[user_id].append({"role": "assistant", "content": assistant_response})
        
        # Ограничение памяти
        if len(user_memory[user_id]) > MAX_MEMORY_MESSAGES:
            user_memory[user_id] = user_memory[user_id][-MAX_MEMORY_MESSAGES:]
        
        # Отправка ответа пользователю
        if is_long_content_request or len(assistant_response) > MAX_MESSAGE_LENGTH:
            await send_long_message(update, assistant_response, get_user_keyboard())
        else:
            await update.message.reply_text(assistant_response, reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text("Не удалось получить ответ от Claude. Попробуйте еще раз.", reply_markup=get_user_keyboard())

# Удаление нежелательных типов сообщений
async def delete_unsupported_message(update: Update, context: CallbackContext):
    try:
        await update.message.delete()
        await update.message.reply_text("Этот тип сообщений не поддерживается. Пожалуйста, отправляйте только текст или фотографии.", reply_markup=get_user_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")

def main():
    # Загрузка данных пользователей
    load_users_data()
    
    # Создание приложения
    builder = Application.builder()
    builder.token(TELEGRAM_BOT_TOKEN)
    # Отключаем job_queue для предотвращения ошибки weak reference
    builder.job_queue(None)
    application = builder.build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик фото
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Удаление всех остальных типов сообщений
    application.add_handler(MessageHandler(
        ~filters.TEXT & ~filters.PHOTO & ~filters.COMMAND, 
        delete_unsupported_message
    ))
    
    # Настраиваем веб-хук для работы на хостингах
    PORT = int(os.environ.get('PORT', '8443'))
    
    # Определяем метод запуска в зависимости от наличия переменной окружения
    if os.environ.get('USE_WEBHOOK', 'False').lower() == 'true':
        # Для запуска на хостинге с веб-хуком
        APP_URL = os.environ.get('APP_URL', '')
        if APP_URL:
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=TELEGRAM_BOT_TOKEN,
                webhook_url=f"{APP_URL}/{TELEGRAM_BOT_TOKEN}"
            )
            print(f"Бот запущен в режиме webhook на порту {PORT}!")
        else:
            print("Ошибка: не указан APP_URL для webhook режима")
            application.run_polling()
    else:
        # Для локального запуска с polling
        print("Бот запущен в режиме polling! Нажмите Ctrl+C для остановки.")
        application.run_polling()

if __name__ == "__main__":
    main() 