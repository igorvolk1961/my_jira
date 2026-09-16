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


def test_requirements_next_is_escaped(client):
    r = client.get('/requirements/create?next=%22%3E%3Cscript%3Ealert(1)%3C/script%3E')
    body = r.get_data(as_text=True)
    assert '<script>alert(1)</script>' not in body
    assert '&lt;script&gt;' in body


def test_current_project_switch(client):
    client.post('/projects/create', data={'name': 'Первый', 'priority_id': '1'})
    client.post('/projects/create', data={'name': 'Второй', 'priority_id': '1'})
    r = client.get('/current-project/2?next=/artifacts/vision')
    assert r.status_code == 302
    body = client.get('/artifacts/vision').get_data(as_text=True)
    assert 'Второй' in body
