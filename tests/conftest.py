"""
Фикстуры pytest. Тесты работают на ОТДЕЛЬНОЙ БД и никогда не трогают рабочую.

Окружение задаётся ДО импорта main, поэтому main.init_db() при импорте
создаёт тестовую БД (data/pytest_verify.db), а не рабочую.

Схема создаётся ОДИН раз (шаблон), затем на каждый тест копируется —
это избегает дорогого повторного создания схемы.
"""

import os
import shutil
import sys

import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)
os.environ['UPO_DATABASE'] = 'pytest_verify.db'
os.environ['UPO_AUDIO_DIR'] = os.path.join('data', 'pytest_audio')

import main  # noqa: E402  (после установки окружения)

TEST_DB = 'pytest_verify.db'
TEMPLATE_DB = 'pytest_template.db'


def _drop(path):
    for suf in ('', '-wal', '-shm', '-journal'):
        if os.path.exists(path + suf):
            os.remove(path + suf)


@pytest.fixture(scope='session', autouse=True)
def _template_db():
    # Гарантированно чистая БД со справочниками -> шаблон для копирования на каждый тест
    _drop(main.db_path_for(TEST_DB))
    main.init_db()
    _drop(main.db_path_for(TEMPLATE_DB))
    shutil.copyfile(main.db_path_for(TEST_DB), main.db_path_for(TEMPLATE_DB))
    yield
    _drop(main.db_path_for(TEMPLATE_DB))


@pytest.fixture()
def app_obj():
    main.app.config.update(TESTING=True)
    return main.app


@pytest.fixture()
def client(_template_db):
    """Свежая БД (копия шаблона) и клиент на каждый тест."""
    shutil.copyfile(main.db_path_for(TEMPLATE_DB), main.db_path_for(TEST_DB))
    shutil.rmtree(main.AUDIO_DIR, ignore_errors=True)
    os.makedirs(main.AUDIO_DIR, exist_ok=True)
    main.app.config.update(TESTING=True)
    with main.app.test_client() as c:
        yield c


def _seed_project(client):
    """Минимальный набор: стейкхолдер, проект, требование, этап, задача, сотрудник (в проекте)."""
    client.post('/stakeholders/create', data={
        'last_name': 'Петров', 'first_name': 'Иван', 'position': 'Директор',
        'type_id': '1', 'priority': '5'})
    client.post('/projects/create', data={
        'name': 'Проект', 'priority_id': '1', 'main_stakeholder_id': '1'})
    client.post('/requirements/create', data={
        'project_id': '1', 'requirement_type_id': '1', 'description': 'Требование', 'priority_id': '1'})
    client.post('/project_stages/create', data={
        'project_id': '1', 'stage_type_id': '1', 'status_id': '1'})
    client.post('/tasks/create', data={
        'requirement_id': '1', 'description': 'Задача', 'stage_id': '1',
        'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    client.post('/employees/create', data={
        'last_name': 'Сидоров', 'first_name': 'Иван', 'position_type_id': '1', 'status_id': '1'})
    client.post('/projects/1/add_employee', data={'employee_id': '1'})


@pytest.fixture()
def seeded(client):
    """Клиент с уже наполненным проектом."""
    _seed_project(client)
    return client
