from app.core.config import get_settings


def path_base() -> str:
    return get_settings().path_base
