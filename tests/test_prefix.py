import os
import sys
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("ALLOWED_CHAT_ID", "1")

# Provide minimal stubs for external packages used by main
openai_stub = types.ModuleType("openai")
openai_stub.ChatCompletion = types.SimpleNamespace()
openai_stub.api_key = ""
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

from main import strip_marv_prefix


class TestStripMarvPrefix(unittest.TestCase):
    def test_strip_prefix_variants(self):
        self.assertEqual(strip_marv_prefix("Marv: hello"), "hello")
        self.assertEqual(strip_marv_prefix("marv:   hi"), "hi")
        self.assertEqual(strip_marv_prefix("MARV:hey"), "hey")
        self.assertEqual(strip_marv_prefix("Hi there"), "Hi there")


if __name__ == "__main__":
    unittest.main()
