
MODULE_NAME: str = __package__.split('.')[0]
PIPELINE_VERSION: str = "0.1"


def _check_pyside6() -> bool:
    try:
        import PySide6
        return True
    except ImportError:
        return False

PYSIDE6_INSTALLED = _check_pyside6()
