"""Артефакты СА, текущий проект и роль «Системный аналитик»."""

import sqlite3

import main

TEST_DB = 'pytest_verify.db'

ARTIFACT_KEYS = [
    'vision', 'glossary', 'stakeholders', 'personas', 'user_stories', 'use_cases',
    'functional_requirements', 'nonfunctional_requirements', 'bpmn', 'state_machines',
    'data_model', 'prototype', 'backlog', 'risks',
]


def _scalar(sql, params=()):
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def _exec(sql, params=()):
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    try:
        con.execute(sql, params)
        con.commit()
    finally:
        con.close()


def _register(client, login='user1', password='pw'):
    client.post('/register', data={'login': login, 'password': password, 'last_name': 'И',
                                   'first_name': 'И', 'middle_name': 'И'})
    return _scalar("SELECT employee_id FROM app_user WHERE login=?", (login,))


def test_all_artifact_pages_render(client):
    client.post('/projects/create', data={'name': 'П', 'priority_id': '1'})
    for key in ARTIFACT_KEYS:
        r = client.get(f'/artifacts/{key}')
        assert r.status_code == 200, key


def test_artifact_pages_render_without_projects(anon_client):
    for key in ARTIFACT_KEYS:
        assert anon_client.get(f'/artifacts/{key}').status_code == 200, key
    assert anon_client.get('/artifacts/nope').status_code == 302


def test_document_artifact_edit_and_render(client):
    client.post('/projects/create', data={'name': 'П', 'priority_id': '1'})
    r = client.post('/artifacts/vision/edit', data={'content': '# Видение\n\n| a | b |\n|---|---|\n| 1 | 2 |'})
    assert r.status_code == 302
    html = client.get('/artifacts/vision').get_data(as_text=True)
    assert '<h1>Видение</h1>' in html and '<table>' in html
    # очистка
    client.get('/artifacts/vision/clear')
    assert 'Артефакт не заполнен' in client.get('/artifacts/vision').get_data(as_text=True)


def test_document_artifact_edit_requires_analyst_or_admin(client):
    client.post('/projects/create', data={'name': 'П', 'priority_id': '1'})
    emp = _register(client, 'u1')
    # обычный пользователь не может
    other = main.app.test_client()
    other.post('/login', data={'login': 'u1', 'password': 'pw'})
    other.post('/artifacts/vision/edit', data={'content': 'X'})
    assert _scalar("SELECT COUNT(*) FROM project_artifact WHERE artifact_key='vision'") == 0
    # аноним не может и перенаправляется на вход
    anon = main.app.test_client()
    r = anon.post('/artifacts/vision/edit', data={'content': 'X'})
    assert r.status_code == 302 and '/login' in r.headers['Location']
    # системный аналитик может
    analyst_pos = _scalar("SELECT id FROM position_type WHERE name='Системный аналитик'")
    _exec("UPDATE employee SET position_type_id=? WHERE id=?", (analyst_pos, emp))
    _exec("UPDATE app_user SET is_analyst=1 WHERE login='u1'")
    other.post('/artifacts/vision/edit', data={'content': 'Y'})
    assert _scalar("SELECT content FROM project_artifact WHERE artifact_key='vision'") == 'Y'


BPMN_XML = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
            'id="Definitions_1" targetNamespace="http://bpmn.io/schema/bpmn">'
            '<bpmn:process id="Process_1" isExecutable="false"/></bpmn:definitions>')


def test_bpmn_artifact_edit_and_view(client):
    client.post('/projects/create', data={'name': 'П', 'priority_id': '1'})
    # пустой артефакт
    empty = client.get('/artifacts/bpmn').get_data(as_text=True)
    assert 'Диаграмма BPMN не заполнена' in empty
    # сохранение XML модельером
    r = client.post('/artifacts/bpmn/edit', data={'content': BPMN_XML})
    assert r.status_code == 302
    assert _scalar("SELECT content FROM project_artifact WHERE artifact_key='bpmn'") == BPMN_XML
    # просмотр в bpmn-js
    view = client.get('/artifacts/bpmn').get_data(as_text=True)
    assert 'bpmn-canvas' in view and 'Process_1' in view and 'bpmn-navigated-viewer' in view
    # страница редактирования подключает модельер
    edit = client.get('/artifacts/bpmn/edit').get_data(as_text=True)
    assert 'bpmn-modeler.production.min.js' in edit and 'bpmn-canvas' in edit
    # очистка
    client.get('/artifacts/bpmn/clear')
    assert 'Диаграмма BPMN не заполнена' in client.get('/artifacts/bpmn').get_data(as_text=True)


def test_bpmn_static_assets_available(client):
    for path in ('/static/bpmn/bpmn-modeler.production.min.js',
                 '/static/bpmn/bpmn-navigated-viewer.production.min.js',
                 '/static/bpmn/assets/bpmn-js.css',
                 '/static/bpmn/assets/diagram-js.css',
                 '/static/bpmn/assets/bpmn-font/css/bpmn-embedded.css'):
        assert client.get(path).status_code == 200, path


def test_bpmn_edit_requires_analyst_or_admin(client):
    client.post('/projects/create', data={'name': 'П', 'priority_id': '1'})
    _register(client, 'u9')
    other = main.app.test_client()
    other.post('/login', data={'login': 'u9', 'password': 'pw'})
    r = other.post('/artifacts/bpmn/edit', data={'content': BPMN_XML})
    assert r.status_code == 302
    assert _scalar("SELECT COUNT(*) FROM project_artifact WHERE artifact_key='bpmn'") == 0


def test_requirements_next_is_escaped(client):
    r = client.get('/requirements/create?next=%22%3E%3Cscript%3Ealert(1)%3C/script%3E')
    body = r.get_data(as_text=True)
    assert '<script>alert(1)</script>' not in body
    assert '&lt;script&gt;' in body


def test_nonfunctional_requirement_types_crud(client):
    client.post('/nonfunctional_requirement_types/create', data={'name': 'Тест-НФТ'})
    assert 'Тест-НФТ' in client.get('/nonfunctional_requirement_types').get_data(as_text=True)
    tid = _scalar("SELECT id FROM nonfunctional_requirement_type WHERE name='Тест-НФТ'")
    client.post(f'/nonfunctional_requirement_types/edit/{tid}', data={'name': 'Тест-НФТ-2'})
    assert 'Тест-НФТ-2' in client.get('/nonfunctional_requirement_types').get_data(as_text=True)
    client.get(f'/nonfunctional_requirement_types/delete/{tid}')
    assert 'Тест-НФТ-2' not in client.get('/nonfunctional_requirement_types').get_data(as_text=True)


def test_nfr_type_used_on_nonfunctional_artifact(client):
    client.post('/projects/create', data={'name': 'П', 'priority_id': '1'})
    nfr_id = _scalar("SELECT id FROM nonfunctional_requirement_type WHERE name='Производительность'")
    nfr_req_type = _scalar("SELECT id FROM requirement_type WHERE name='Нефункциональное требование'")
    client.post('/requirements/create', data={'project_id': '1', 'requirement_type_id': str(nfr_req_type),
                                              'nfr_type_id': str(nfr_id), 'description': 'Отклик < 1с',
                                              'priority_id': '1'})
    body = client.get('/artifacts/nonfunctional_requirements').get_data(as_text=True)
    assert 'Тип НФТ' in body and 'Производительность' in body and 'Отклик' in body
    # селект типа НФТ берётся из нового справочника
    form = client.get('/requirements/create').get_data(as_text=True)
    assert 'name="nfr_type_id"' in form and 'Производительность' in form
    # тип НФТ виден в карточке требования
    assert 'Производительность' in client.get('/requirements/1').get_data(as_text=True)


def test_current_project_switch(client):
    client.post('/projects/create', data={'name': 'Первый', 'priority_id': '1'})
    client.post('/projects/create', data={'name': 'Второй', 'priority_id': '1'})
    r = client.get('/current-project/2?next=/artifacts/vision')
    assert r.status_code == 302
    body = client.get('/artifacts/vision').get_data(as_text=True)
    assert 'Второй' in body
