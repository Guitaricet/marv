import os
import sys
import types
import importlib
import pytest

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("ALLOWED_CHAT_ID", "1")

class DummyTokenizer:
    def encode(self, text):
        return []

    def decode(self, tokens):
        return ""

@pytest.fixture(autouse=True)
def stub_modules():
    openai = types.SimpleNamespace(api_key="", ChatCompletion=types.SimpleNamespace(create=lambda *a, **k: None))
    tiktoken = types.SimpleNamespace(encoding_for_model=lambda name: DummyTokenizer())
    aiofiles = types.ModuleType("aiofiles")
    loguru = types.ModuleType("loguru")
    loguru.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
    telegram = types.ModuleType("telegram")
    telegram.Update = type("Update", (), {})
    telegram.Message = type("Message", (), {})
    telegram_ext = types.ModuleType("telegram.ext")
    telegram_ext.Application = type("Application", (), {})
    telegram_ext.CommandHandler = type("CommandHandler", (), {})
    telegram_ext.MessageHandler = type("MessageHandler", (), {})
    telegram_ext.CallbackContext = type("CallbackContext", (), {})
    telegram_ext.filters = types.SimpleNamespace(
        MessageFilter=type("MessageFilter", (), {}),
        Message=type("Message", (), {}),
        MessageEntity=types.SimpleNamespace(BOT_COMMAND="bot_command"),
        ALL=None,
        Chat=lambda chat_id=None: None,
    )

    modules = {
        "openai": openai,
        "tiktoken": tiktoken,
        "aiofiles": aiofiles,
        "loguru": loguru,
        "telegram": telegram,
        "telegram.ext": telegram_ext,
    }
    original = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        yield
    finally:
        for name, mod in original.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

def load_main(tmp_path):
    if "main" in sys.modules:
        importlib.reload(sys.modules["main"])
    else:
        importlib.import_module("main")
    import main
    main.message_storage = []
    main.MESSAGE_STORAGE_PATH = str(tmp_path / "messages.jsonl")
    return main

