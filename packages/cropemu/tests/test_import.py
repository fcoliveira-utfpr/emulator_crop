import cropemu


def test_version():
    from importlib.metadata import version
    assert cropemu.__version__ == version("cropemu")
