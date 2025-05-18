import importlib

def test_strip_prefix_variants(tmp_path):
    main = importlib.import_module('main')
    main = importlib.reload(main)
    main.message_storage = []
    main.MESSAGE_STORAGE_PATH = str(tmp_path / 'messages.jsonl')
    strip = main.strip_marv_prefix
    assert strip('Marv: hello') == 'hello'
    assert strip('marv:   hi') == 'hi'
    assert strip('MARV:hey') == 'hey'
    assert strip('Hi there') == 'Hi there'
