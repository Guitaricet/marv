import os
import openai
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI API
openai.api_key = os.environ["OPENAI_API_KEY"]

SYSTEM_MESSAGE_EN = "You are an AI assistant that summarizes conversations."
SYSTEM_MESSAGE_RU = "Ты - ИИ-помощник, который суммирует разговоры. Иногда ты вставляешь шутки в саммари для рофлов"

class NonCommandMessageFilter(filters.MessageFilter):
    def filter(self, message: filters.Message):
        return not any(entity.type == filters.MessageEntity.BOT_COMMAND for entity in message.entities)

# Initialize message storage
message_storage = []

async def handle_message(update: Update, context):
    print("Received message")
    msg = update.message.text
    timestamp = update.message.date.timestamp()
    user = update.message.from_user.first_name

    print(f"Received message from {user}: {msg}")
    logger.info(f"Received message from {user}: {msg}")

    message_storage.append({"timestamp": timestamp, "user": user, "message": msg})

async def summarize_messages(start_time=None, end_time=None):
    logger.info(f"Summarizing messages from {start_time} to {end_time}")

    messages_to_summarize = []

    for msg in message_storage:
        if (start_time is None or msg["timestamp"] >= start_time) and (end_time is None or msg["timestamp"] <= end_time):
            messages_to_summarize.append(f"{msg['user']}: {msg['message']}")

    conversation = "\n".join(messages_to_summarize)

    logger.info(f"Conversation to summarize:\n{conversation}")

    openai_chat = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_MESSAGE_RU},
            {"role": "user", "content": conversation},
        ]
    )

    summary = openai_chat.choices[0].message["content"]
    return summary.strip()

async def summarize(update: Update, context):
    logger.debug("Received /summarize command")
    start_time = None
    end_time = None

    if len(context.args) >= 2:
        try:
            start_time = float(context.args[0])
            end_time = float(context.args[1])
        except ValueError:
            await update.message.reply_text("Invalid start and end time. Please enter them as UNIX timestamps.")
            return

    summary = await summarize_messages(start_time, end_time)
    await update.message.reply_text(summary)

async def debug_handler(update: Update, context):
    # print("Debug: ", update)
    pass


if __name__ == "__main__":
    application = Application.builder().token(os.environ["TG_BOT_TOKEN"]).build()

    non_command_filter = NonCommandMessageFilter()
    application.add_handler(MessageHandler(non_command_filter, handle_message))
    application.add_handler(CommandHandler("summarize", summarize))
    application.add_handler(MessageHandler(filters.ALL, debug_handler))  # Move the debug_handler to the end

    application.run_polling(1.0)
