def test_imports():
    """Простая проверка импорта библиотек"""
    try:
        import flask
        import numpy
        import PIL
        import matplotlib
        assert True
    except ImportError as e:
        assert False, f"Ошибка импорта: {e}"
