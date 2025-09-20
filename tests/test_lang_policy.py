from app.utils.language import detect_lang
def test_detect_lang():
    assert detect_lang("مرحبا") == "ar"
    assert detect_lang("hello") == "en"
