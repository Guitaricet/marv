import os
import time
import json
import logging

import openai
import aiofiles
import tiktoken
from loguru import logger
from telegram import Update, Message
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters

import bot_strings


# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI API
openai.api_key = os.environ["OPENAI_API_KEY"]

OPENAI_MODEL_NAME = "gpt-3.5-turbo"
MAX_CONTEXT_LENGTH = 4096 - 256
BOT_NAME = "Marv"
ALLOWED_CHAT_ID = -1001304517416
SYSTEM_MESSAGE_EN = "You are an AI assistant Marv that make detailed summarizes of russian conversations. For longer requests you will have longer summaries. Make sure to mention all of the jokes in detail. Add some jokes to the summary in the style of Marvin from the Hitchhiker's guide to the galaxy."
SYSTEM_MESSAGE_RU = "Ты - ИИ-помощник Marv, который суммирует разговоры и пишет саммари на русском языке. Обязательно упомяни все шутки подробно. Иногда (очень редко) добавляй в саммари шутки в стиле Марвина из Hitchhiker's guide to the galaxy."
SYSTEM_MESSAGE_RESPOND_EN = "You are an AI fridnd Marv that responds to messages. You read the history and respond based on it. Respond them like a human would do. Add some Marvin (Hitchhiker's guide to the galaxy) jokes. You are allowed to be rude and make friendly banter."

MESSAGE_STORAGE_PATH = "state/message_storage.jsonl"
HELP_HISTORY_PATH = "state/help_history.txt"

lang_to_system_message = {
    "en": SYSTEM_MESSAGE_EN,
    "ru": SYSTEM_MESSAGE_RU,
}

tokenizer = tiktoken.encoding_for_model(OPENAI_MODEL_NAME)

def truncate(text, max_tokens):
    encoded_text = tokenizer.encode(text)
    if len(encoded_text) < max_tokens:
        return text

    encoded_text = encoded_text[-max_tokens:]
    return tokenizer.decode(encoded_text)


class NonCommandMessageFilter(filters.MessageFilter):
    def filter(self, message: filters.Message):
        return not any(entity.type == filters.MessageEntity.BOT_COMMAND for entity in message.entities)

class MentionFilter(filters.MessageFilter):
    def __init__(self, usernames: str):
        super().__init__()
        if isinstance(usernames, str):
            usernames = [usernames]
        self.usernames = usernames

    def filter(self, message):
        if message.text is None:
            return False

        return any(n.lower() in message.text.lower() for n in self.usernames)

class ReplyToFilter(filters.MessageFilter):
    def __init__(self, names):
        super().__init__()
        if isinstance(names, str):
            names = [names]
        self.names = names

    async def filter_async(self, message: Message):
        logger.info(f"Checking if message is a reply to the bot. Message: {message}")
        if not message.reply_to_message:
            return False

        logger.info(f"Checking if message is a reply to the bot. User: {message.reply_to_message.from_user}")
        # Check if the message is a reply to the bot
        return any(message.reply_to_message.from_user.username.lower() == n.lower() for n in self.names)


async def save_message_to_storage(message: dict):
    async with aiofiles.open(MESSAGE_STORAGE_PATH, mode="a") as storage_file:
        await storage_file.write(json.dumps(message, ensure_ascii=False) + "\n")

# Initialize message storage
# I want to keep this call close to handle_message definition
message_storage = []

if os.path.exists(MESSAGE_STORAGE_PATH):
    with open(MESSAGE_STORAGE_PATH, mode="r") as f:
        for line in f:
            if len(line) < 2:  # <2 because just \n doesn't work on GCP for some reason
                continue
            message_storage.append(json.loads(line))

async def handle_message(update: Update, context):
    msg = update.message.text
    timestamp = update.message.date.timestamp()
    user = update.message.from_user.first_name
    user_id = update.message.from_user.id

    print(f"Received message from {user}: {msg}")
    logger.info(f"Received message from {user}: {msg}")

    print("chat ID: ", update.message.chat_id)

    message = {"timestamp": timestamp, "user": user, "user_id": user_id, "message": msg}
    message_storage.append(message)
    await save_message_to_storage(message)


async def handle_reply(update: Update, context: CallbackContext):
    logger.info(f"Handling reply for update: {update}")
    await handle_message_to_bot(update, context)


async def handle_mention(update: Update, context: CallbackContext):
    logger.info(f"Handling mention for update: {update}")
    await handle_message_to_bot(update, context)


async def handle_message_to_bot(update: Update, context: CallbackContext):
    await handle_message(update, context)

    user = update.message.from_user.first_name
    message = update.message.text
    full_history = "\n".join([f"{msg['user']}: {msg['message']}" for msg in message_storage[-100:]])
    full_history = truncate(full_history, MAX_CONTEXT_LENGTH)

    logger.info(f"Replying with the history: {full_history}")

    openai_chat = openai.ChatCompletion.create(
        model=OPENAI_MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_MESSAGE_RESPOND_EN},
            {"role": "user", "content": "the next message is the full context of the conversation, use it fully to reply"},
            {"role": "user", "content": full_history},
            {"role": "user", "content": "now, if the history is relevant, use it to answer this quesiton. If it's not just make something up"},
            {"role": "user", "content": f"{user}: {message}"},
        ]
    )

    response = openai_chat.choices[0].message["content"].strip()
    message = {"timestamp": time.time(), "user": BOT_NAME, "user_id": -42, "message": response}

    message_storage.append(message)
    await save_message_to_storage(message)

    await update.message.reply_text(response)


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
    conversation = truncate(conversation, MAX_CONTEXT_LENGTH)

    messages = [
        {"role": "system", "content": lang_to_system_message[lang]},
        {"role": "user", "content": conversation},
    ]

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
    logger.info("Current prompts:")
    logger.info(SYSTEM_MESSAGE_EN + "\n\n")
    logger.info(SYSTEM_MESSAGE_RU + "\n\n")
    logger.info(SYSTEM_MESSAGE_RESPOND_EN + "\n\n")

    application = Application.builder().token(os.environ["TG_BOT_TOKEN"]).build()

    non_command_filter = NonCommandMessageFilter()
    allowed_chat_filter = filters.Chat(chat_id=ALLOWED_CHAT_ID)
    mention_filter = MentionFilter(usernames=[BOT_NAME, "марв", "cycloeblan_bot"])
    reply_to_bot_filter = ReplyToFilter(names=[BOT_NAME, "марв", "cycloeblan_bot"])

    application.add_handler(MessageHandler(mention_filter & allowed_chat_filter, handle_mention))
    application.add_handler(MessageHandler(reply_to_bot_filter & allowed_chat_filter, handle_reply))
    application.add_handler(MessageHandler(non_command_filter & allowed_chat_filter, handle_message))
    application.add_handler(CommandHandler("summarize", summarize, filters=allowed_chat_filter))
    application.add_handler(CommandHandler("help", help_command, filters=allowed_chat_filter))
    application.add_handler(CommandHandler("get_chat_id", get_chat_id, filters=allowed_chat_filter))
    application.add_handler(MessageHandler(filters.ALL, debug_handler))

    application.run_polling(1.0)
