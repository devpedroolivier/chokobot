from app.settings import DEFAULT_STORE_CLOSED_NOTICE, get_settings


def is_store_closed() -> bool:
    return False


def get_store_closed_notice() -> str:
    return get_settings().store_closed_notice


def __getattr__(name: str):
    settings = get_settings()
    mapping = {
        "ZAPI_TOKEN": settings.zapi_token,
        "ZAPI_BASE": settings.zapi_base,
        "ZAPI_ENDPOINT_TEXT": settings.zapi_endpoint_text,
        "ZAPI_ENDPOINT_IMAGE": settings.zapi_endpoint_image,
        "CAFETERIA_URL": settings.cafeteria_url,
        "DOCES_URL": settings.doces_url,
        "STORE_CLOSED_NOTICE": settings.store_closed_notice or DEFAULT_STORE_CLOSED_NOTICE,
    }
    if name in mapping:
        return mapping[name]
    raise AttributeError(name)
