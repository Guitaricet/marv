import os
import unittest
import tempfile
import os
import sys
import types
import tempfile
import unittest
from types import SimpleNamespace
from datetime import datetime

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("ALLOWED_CHAT_ID", "1")

# Stub out external dependencies so that main can be imported
openai_stub = types.ModuleType("openai")

class FakeOpenAI:
    def __init__(self, *args, **kwargs):
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda *a, **k: None)
        )

openai_stub.OpenAI = FakeOpenAI
sys.modules.setdefault("openai", openai_stub)

tiktoken_stub = types.ModuleType("tiktoken")

class DummyTokenizer:
    def encode(self, text):
        return []

    def decode(self, tokens):
        return ""


def encoding_for_model(name):
    return DummyTokenizer()

tiktoken_stub.encoding_for_model = encoding_for_model
sys.modules.setdefault("tiktoken", tiktoken_stub)

aiofiles_stub = types.ModuleType("aiofiles")
sys.modules.setdefault("aiofiles", aiofiles_stub)

loguru_stub = types.ModuleType("loguru")
loguru_stub.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
sys.modules.setdefault("loguru", loguru_stub)

telegram_stub = types.ModuleType("telegram")
telegram_stub.Update = type("Update", (), {})
telegram_stub.Message = type("Message", (), {})
sys.modules.setdefault("telegram", telegram_stub)

telegram_ext_stub = types.ModuleType("telegram.ext")

class DummyFilter:
    pass

telegram_ext_stub.Application = type("Application", (), {})
telegram_ext_stub.CommandHandler = type("CommandHandler", (), {})
telegram_ext_stub.MessageHandler = type("MessageHandler", (), {})
telegram_ext_stub.CallbackContext = type("CallbackContext", (), {})
telegram_ext_stub.filters = types.SimpleNamespace(
    MessageFilter=DummyFilter,
    Message=type("Message", (), {}),
    MessageEntity=types.SimpleNamespace(BOT_COMMAND="bot_command"),
    ALL=None,
    Chat=lambda chat_id=None: None,
)
sys.modules.setdefault("telegram.ext", telegram_ext_stub)

import main


class FakeMessage:
    def __init__(self, text):
        self.text = text
        self.date = datetime.now()
        self.from_user = SimpleNamespace(first_name="Alice", id=123)
        self.chat_id = 1
        self.replied_text = None

    async def reply_text(self, text):
        self.replied_text = text


class FakeUpdate:
    def __init__(self, text):
        self.message = FakeMessage(text)


class FakeContext:
    pass


class TestHandleMessageToBot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_storage = main.message_storage
        main.message_storage = []
        self.original_path = main.MESSAGE_STORAGE_PATH
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        self.temp_path = tmp.name
        main.MESSAGE_STORAGE_PATH = self.temp_path

    async def asyncTearDown(self):
        main.message_storage = self.original_storage
        main.MESSAGE_STORAGE_PATH = self.original_path
        if os.path.exists(self.temp_path):
            os.remove(self.temp_path)

    async def test_handle_message_removes_prefix(self):
        async def fake_handle_message(update, context):
            pass

        async def fake_save(message):
            pass

        def fake_create(*args, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message={"content": "Marv: ping"})])

        original_handle = main.handle_message
        original_save = main.save_message_to_storage
        original_create = main.client.chat.completions.create

        main.handle_message = fake_handle_message
        main.save_message_to_storage = fake_save
        main.client.chat.completions.create = fake_create

        try:
            update = FakeUpdate("hello")
            await main.handle_message_to_bot(update, FakeContext())
            self.assertEqual(update.message.replied_text, "ping")
            self.assertEqual(main.message_storage[-1]["message"], "ping")
        finally:
            main.handle_message = original_handle
            main.save_message_to_storage = original_save
            main.client.chat.completions.create = original_create


if __name__ == "__main__":
    unittest.main()
