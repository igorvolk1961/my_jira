"""Сборка FastAPI-приложения УПО."""

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import BASE_DIR, secret_key
from app.db.schema import ensure_database
from app.errors import register_exception_handlers
from app.urls import build_route_param_names, install_relative_url_for


def create_app() -> FastAPI:
    install_relative_url_for()
    application = FastAPI(title="Учебный проектный офис", docs_url=None, redoc_url=None)

    application.add_middleware(SessionMiddleware, secret_key=secret_key(), same_site="lax")

    static_dir = os.path.join(BASE_DIR, "static")
    if os.path.isdir(static_dir):
        application.mount("/static", StaticFiles(directory=static_dir), name="static")

    register_exception_handlers(application)

    # Инициализация БД при импорте (важно для uvicorn/gunicorn, где main.py не __main__)
    ensure_database()

    from app.api import api_router

    application.include_router(api_router)
    application.state.route_param_names = build_route_param_names(application)
    return application


app = create_app()
