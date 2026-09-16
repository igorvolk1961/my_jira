"""Фикстуры pytest. Тесты работают на ОТДЕЛЬНОЙ БД и никогда не трогают рабочую.

Окружение задаётся ДО импорта приложения, поэтому ensure_database() при импорте
создаёт тестовую БД (data/pytest_verify.db), а не рабочую.
Схема создаётся один раз (шаблон), затем на каждый тест копируется файлом.
"""

import os
import shutil
import sys

import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)
os.environ["UPO_DATABASE"] = "pytest_verify.db"
os.environ["UPO_AUDIO_DIR"] = os.path.join("data", "pytest_audio")
os.environ.setdefault("UPO_SECRET_KEY", "test-secret-key")

from fastapi.testclient import TestClient  # noqa: E402
from httpx import Response as _HttpxResponse  # noqa: E402

from app.config import AUDIO_DIR, db_path_for  # noqa: E402
from app.db.engine import dispose_all  # noqa: E402
from app.db.schema import ensure_database  # noqa: E402
from app.main import app  # noqa: E402

TEST_DB = "pytest_verify.db"
TEMPLATE_DB = "pytest_template.db"


# --- Совместимость с Flask-тестами: get_data()/mimetype у httpx.Response ---
if not hasattr(_HttpxResponse, "get_data"):

    def _get_data(self, as_text=False):  # type: ignore[no-untyped-def]
        return self.text if as_text else self.content

    _HttpxResponse.get_data = _get_data  # type: ignore[attr-defined]

if not hasattr(_HttpxResponse, "mimetype"):

    @property
    def _mimetype(self):  # type: ignore[no-untyped-def]
        return (self.headers.get("content-type") or "").split(";")[0].strip()

    _HttpxResponse.mimetype = _mimetype  # type: ignore[attr-defined]

if not hasattr(_HttpxResponse, "get_json"):

    def _get_json(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.json(**kwargs)

    _HttpxResponse.get_json = _get_json  # type: ignore[attr-defined]


def _test_client() -> TestClient:
    return TestClient(app, follow_redirects=False)


def _drop(path):
    for suf in ("", "-wal", "-shm", "-journal"):
        if os.path.exists(path + suf):
            os.remove(path + suf)


@pytest.fixture(scope="session", autouse=True)
def _template_db():
    """Чистая БД со справочниками -> шаблон для копирования на каждый тест."""
    dispose_all()
    _drop(db_path_for(TEST_DB))
    ensure_database(db_path_for(TEST_DB))
    _drop(db_path_for(TEMPLATE_DB))
    shutil.copyfile(db_path_for(TEST_DB), db_path_for(TEMPLATE_DB))
    yield
    dispose_all()
    _drop(db_path_for(TEMPLATE_DB))


def _fresh_db():
    dispose_all()
    _drop(db_path_for(TEST_DB))
    shutil.copyfile(db_path_for(TEMPLATE_DB), db_path_for(TEST_DB))
    shutil.rmtree(AUDIO_DIR, ignore_errors=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)


@pytest.fixture()
def app_obj():
    return app


@pytest.fixture()
def client(_template_db):
    """Свежая БД (копия шаблона) и клиент-администратор на каждый тест."""
    _fresh_db()
    with _test_client() as c:
        c.post("/login", data={"login": "admin", "password": "12345"})
        yield c


@pytest.fixture()
def anon_client(_template_db):
    """Свежая БД и анонимный клиент (без входа)."""
    _fresh_db()
    with _test_client() as c:
        yield c


@pytest.fixture()
def user_client(_template_db):
    """Свежая БД и клиент-пользователь (регистрация + вход)."""
    _fresh_db()
    with _test_client() as c:
        c.post(
            "/register",
            data={
                "login": "user1",
                "password": "pw",
                "last_name": "Иванов",
                "first_name": "Иван",
                "middle_name": "Иванович",
            },
        )
        c.post("/login", data={"login": "user1", "password": "pw"})
        yield c


def _seed_project(client):
    """Минимальный набор: стейкхолдер, проект, требование, этап, задача, сотрудник."""
    client.post(
        "/stakeholders/create",
        data={"last_name": "Петров", "first_name": "Иван", "position": "Директор", "type_id": "1", "priority": "5"},
    )
    client.post("/projects/create", data={"name": "Проект", "priority_id": "1", "main_stakeholder_id": "1"})
    client.post(
        "/requirements/create",
        data={"project_id": "1", "requirement_type_id": "1", "description": "Требование", "priority_id": "1"},
    )
    client.post("/project_stages/create", data={"project_id": "1", "stage_type_id": "1", "status_id": "1"})
    client.post(
        "/tasks/create",
        data={
            "requirement_id": "1",
            "description": "Задача",
            "stage_id": "1",
            "task_type_id": "1",
            "priority_id": "1",
            "status_id": "1",
        },
    )
    client.post(
        "/employees/create",
        data={"last_name": "Сидоров", "first_name": "Иван", "position_type_id": "1", "status_id": "1"},
    )
    client.post("/projects/1/add_employee", data={"employee_id": "1"})


@pytest.fixture()
def seeded(client):
    """Клиент с уже наполненным проектом."""
    _seed_project(client)
    return client
