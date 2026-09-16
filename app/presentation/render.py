"""Рендеринг Jinja2-шаблонов и общий контекст страниц."""

import os

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from markdown_it import MarkdownIt
from sqlalchemy.orm import Session

from app.dependencies import current_db_name, current_project, current_user
from app.flash import take_flashes
from app.presentation.capabilities import can_edit_artifacts, is_admin, is_analyst

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@pass_context
def _safe_url_for(ctx, name, **params):
    """url_for, устойчивый к ещё не зарегистрированным маршрутам (время миграции)."""
    request = ctx.get("request")
    if request is None:
        return "#"
    try:
        return str(request.url_for(name, **params))
    except Exception:
        return "#"


templates.env.globals["url_for"] = _safe_url_for

_markdown_renderer: MarkdownIt | None = None


def render_markdown(value: str | None) -> str:
    """Markdown → HTML (gfm-like, без сырого HTML)."""
    global _markdown_renderer
    if _markdown_renderer is None:
        _markdown_renderer = MarkdownIt("gfm-like", {"html": False, "linkify": False})
    return _markdown_renderer.render(value or "")


templates.env.filters["markdown"] = render_markdown


def build_context(request: Request, db: Session, **extra: object) -> dict[str, object]:
    user = current_user(request, db)
    project = current_project(request, db)
    context: dict[str, object] = {
        "request": request,
        "current_user": user,
        "is_admin": is_admin(user),
        "is_analyst": is_analyst(user),
        "can_edit_artifacts": can_edit_artifacts(user),
        "current_project": project,
        "current_db": current_db_name(request),
        "flashes": take_flashes(request),
    }
    context.update(extra)
    return context


def render(request: Request, template: str, db: Session, **extra: object) -> HTMLResponse:
    return templates.TemplateResponse(request, template, build_context(request, db, **extra))
