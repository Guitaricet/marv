import importlib
from types import SimpleNamespace
from datetime import datetime
import pytest

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

@pytest.mark.asyncio
async def test_handle_message_to_bot(tmp_path):
    main = importlib.import_module('main')
    main = importlib.reload(main)
    main.message_storage = []
    main.MESSAGE_STORAGE_PATH = str(tmp_path / 'messages.jsonl')

    async def fake_save(message):
        pass
    main.save_message_to_storage = fake_save

    def fake_create(*args, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message={"content": "Marv: ping"})])
    main.openai.ChatCompletion.create = fake_create

    update = FakeUpdate('hello')
    await main.handle_message_to_bot(update, SimpleNamespace())
    assert update.message.replied_text == 'ping'
    assert main.message_storage[-1]["message"] == 'ping'
