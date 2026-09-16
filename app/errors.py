"""Исключения-редиректы и их обработчики (замена Flask before_request-редиректов)."""

from starlette.requests import Request
from starlette.responses import RedirectResponse


class AuthRedirect(Exception):
    """Не авторизован: 302 на /login с сохранением исходного пути в сессии."""

    def __init__(self, next_url: str | None = None) -> None:
        self.next_url = next_url


class ForbiddenRedirect(Exception):
    """Недостаточно прав: flash + 302 на главную."""

    def __init__(self, message: str, target: str = "index") -> None:
        self.message = message
        self.target = target


def register_exception_handlers(app) -> None:
    @app.exception_handler(AuthRedirect)
    async def _auth_redirect(request: Request, exc: AuthRedirect):
        if exc.next_url is not None:
            request.session["next"] = exc.next_url
        return RedirectResponse(request.url_for("login"), status_code=302)

    @app.exception_handler(ForbiddenRedirect)
    async def _forbidden_redirect(request: Request, exc: ForbiddenRedirect):
        from app.flash import flash

        flash(request, exc.message, "error")
        return RedirectResponse(request.url_for(exc.target), status_code=302)
