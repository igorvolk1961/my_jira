"""Flash-сообщения поверх сессии (аналог Flask flash/get_flashed_messages)."""

from starlette.requests import Request

_KEY = "_flashes"


def flash(request: Request, message: str, category: str = "success") -> None:
    flashes = list(request.session.get(_KEY) or [])
    flashes.append([category, message])
    request.session[_KEY] = flashes


def take_flashes(request: Request) -> list[tuple[str, str]]:
    flashes = request.session.pop(_KEY, None) or []
    return [(str(category), str(message)) for category, message in flashes]
