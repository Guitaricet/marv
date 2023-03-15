import os
import time
import json
import logging

import openai
import aiofiles
import jsonlines
from loguru import logger
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

import bot_strings


# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI API
openai.api_key = os.environ["OPENAI_API_KEY"]

ALLOWED_CHAT_ID = -1001304517416
SYSTEM_MESSAGE_EN = "You are an AI assistant that make detailed summarizes of russian conversations between 4 friends: Anna, Vlad, Vika, and Lena in english. For longer requests you will have longer summaries. Make sure to mention all of the jokes in detail. Add some jokes to the summary in the style of Marvin from the Hitchhiker's guide to the galaxy."
SYSTEM_MESSAGE_RU = "Ты - ИИ-помощник, который суммирует разговоры и пишет саммари на русском языке. Обязательно упомяни все шутки подробно. Иногда (очень редко) добавляй в саммари шутки в стиле Марвина из Hitchhiker's guide to the galaxy."

MESSAGE_STORAGE_PATH = "state/message_storage.jsonl"
HELP_HISTORY_PATH = "state/help_history.txt"

lang_to_system_message = {
    "en": SYSTEM_MESSAGE_EN,
    "ru": SYSTEM_MESSAGE_RU,
}


class NonCommandMessageFilter(filters.MessageFilter):
    def filter(self, message: filters.Message):
        return not any(entity.type == filters.MessageEntity.BOT_COMMAND for entity in message.entities)


async def save_message_to_storage(message: dict):
    async with aiofiles.open(MESSAGE_STORAGE_PATH, mode="a") as storage_file:
        await storage_file.write(json.dumps(message, ensure_ascii=False) + "\n")

# Initialize message storage
# I want to keep this call close to handle_message definition
message_storage = []

if os.path.exists(MESSAGE_STORAGE_PATH):
    with jsonlines.open(MESSAGE_STORAGE_PATH, mode="r") as f:
        for message in f:
            message_storage.append(message)

async def handle_message(update: Update, context):
    msg = update.message.text
    timestamp = update.message.date.timestamp()
    user = update.message.from_user.first_name
    user_id = update.message.from_user.id

    print(f"Received message from {user}: {msg}")
    logger.info(f"Received message from {user}: {msg}")

    message = {"timestamp": timestamp, "user": user, "user_id": user_id, "message": msg}
    message_storage.append(message)
    await save_message_to_storage(message)


def get_filtered_messages(user_id, hours=None):
    current_timestamp = time.time()

    if hours is not None:
        earliest_timestamp = current_timestamp - (hours * 3600)
    else:
        user_messages = [msg for msg in message_storage if msg["user_id"] == user_id]
        if user_messages:
            earliest_timestamp = user_messages[-1]["timestamp"]
        else:
            earliest_timestamp = 0

        # if earliest timestamp is less than 1 hour ago, set it to 1 hour ago
        if current_timestamp - earliest_timestamp < 3600:
            earliest_timestamp = current_timestamp - 3600

        # if earliest timestamp is more than 24 hours ago, set it to 24 hours ago
        if current_timestamp - earliest_timestamp > 86400:
            earliest_timestamp = current_timestamp - 86400
        
        # if earliest timestamp is more than the last summary, set it to the last summary
        last_summary = [msg for msg in message_storage if msg["user"] == "summary"]
        if last_summary:
            last_summary_timestamp = last_summary[-1]["timestamp"]
            if last_summary_timestamp > earliest_timestamp:
                earliest_timestamp = last_summary_timestamp

    return [
        msg for msg in message_storage if msg["timestamp"] >= earliest_timestamp and msg["user"] != "summary"
    ]


def summarize_messages(messages, lang="en"):
    messages_to_summarize = [f"{msg['user']}: {msg['message']}" for msg in messages]
    conversation = " ".join(messages_to_summarize)

    messages = [
        {"role": "system", "content": lang_to_system_message[lang]},
        {"role": "user", "content": conversation},
    ]
    print(messages)
    openai_chat = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )

    summary = openai_chat.choices[0].message["content"]
    summary = summary.strip()

    message_storage.append({"timestamp": time.time(), "user": "summary", "user_id": -1, "message": summary})
    return summary


async def summarize(update: Update, context: CallbackContext) -> None:
    logger.info(f"Received /summarize command from {update.message.from_user.first_name}.")
    user_id = update.message.from_user.id

    hours = None
    lang = "en"
    if context.args:
        try:
            hours = float(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid input. Please provide a valid number of hours.")
            return

        try:
            lang = context.args[1]
            logger.info(f"Language is {lang}")
            if lang not in ["en", "ru"]:
                await update.message.reply_text(f"I didn't understand the language {lang}. Please use 'en' or 'ru'. Using 'en' by default.")
                lang = "en"
        except IndexError:
            lang = "en"

    filtered_messages = get_filtered_messages(user_id, hours)
    summary = summarize_messages(filtered_messages, lang)
    await update.message.reply_text(summary)


async def help_command(update: Update, context: CallbackContext) -> None:
    logger.info(f"Received /help command from {update.message.from_user.first_name}.")
    openai_chat = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Repharse this text with minimal changes, keep the style and ((format)) it nicely."},
            {"role": "user", "content": bot_strings.HELP_MESSAGE},
        ]
    )

    summary = openai_chat.choices[0].message["content"]

    # save into file, append to file
    with open(HELP_HISTORY_PATH, mode="a") as f:
        f.write("<start>\n" + summary + "\n<end>\n")

    await update.message.reply_text(summary)


async def debug_handler(update: Update, context):
    # print("Debug: ", update)
    pass

async def get_chat_id(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    await update.message.reply_text(f"Chat ID: {chat_id}")
    logger.info(f"Received /get_chat_id command from {update.message.from_user.first_name}.")
    logger.info(f"Chat ID: {chat_id}")


if __name__ == "__main__":
    application = Application.builder().token(os.environ["TG_BOT_TOKEN"]).build()

    non_command_filter = NonCommandMessageFilter()
    # allowed_chat_filter = filters.Chat(chat_id=ALLOWED_CHAT_ID)

    # application.add_handler(MessageHandler(non_command_filter & allowed_chat_filter, handle_message))
    application.add_handler(MessageHandler(non_command_filter, handle_message))
    application.add_handler(CommandHandler("summarize", summarize))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("get_chat_id", get_chat_id))
    application.add_handler(MessageHandler(filters.ALL, debug_handler))  # Move the debug_handler to the end

    application.run_polling(1.0)
