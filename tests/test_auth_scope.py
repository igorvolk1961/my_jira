"""Аутентификация, авторизация, аудит, чат, автор назначения."""

import sqlite3

import main

TEST_DB = 'pytest_verify.db'


def _scalar(sql, params=()):
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def _status_id(name):
    return _scalar("SELECT id FROM task_status WHERE name=?", (name,))


def _seed_project_with_user(client):
    """Пользователь user1, проект с задачей 1, задача назначена сотруднику user1. Возвращает employee_id."""
    client.post('/register', data={'login': 'user1', 'password': 'pw', 'last_name': 'Иванов',
                                   'first_name': 'Иван', 'middle_name': 'Иванович'})
    emp = _scalar("SELECT employee_id FROM app_user WHERE login='user1'")
    client.post('/stakeholders/create', data={'last_name': 'Петров', 'first_name': 'Иван',
                                              'type_id': '1', 'priority': '3'})
    client.post('/projects/create', data={'name': 'П', 'priority_id': '1'})
    client.post('/requirements/create', data={'project_id': '1', 'requirement_type_id': '1',
                                              'description': 'R', 'priority_id': '1'})
    client.post('/project_stages/create', data={'project_id': '1', 'stage_type_id': '1', 'status_id': '1'})
    client.post('/tasks/create', data={'requirement_id': '1', 'description': 'T', 'stage_id': '1',
                                       'task_type_id': '1', 'priority_id': '1', 'status_id': '1'})
    client.post('/projects/1/add_employee', data={'employee_id': str(emp)})
    client.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'task',
                                                  'employee_id': str(emp), 'share': '1.0'})
    return emp


def _login_user(client):
    client.get('/logout')
    client.post('/login', data={'login': 'user1', 'password': 'pw'})


# ---------- Анонимный доступ ----------

def test_anonymous_can_read_but_not_write(anon_client):
    assert anon_client.get('/').status_code == 200
    assert anon_client.get('/projects').status_code == 200
    assert anon_client.get('/tasks').status_code == 200
    r = anon_client.post('/tasks/create', data={'description': 'X'})
    assert r.status_code == 302 and '/login' in r.headers['Location']
    assert _scalar("SELECT COUNT(*) FROM task") == 0
    # GET-удаление тоже защищено
    r = anon_client.get('/priorities/delete/1')
    assert r.status_code == 302 and '/login' in r.headers['Location']
    assert _scalar("SELECT COUNT(*) FROM priority WHERE id=1 AND is_deleted=0") == 1


def test_admin_is_seeded(client):
    assert _scalar("SELECT COUNT(*) FROM app_user WHERE login='admin' AND role='admin'") == 1


# ---------- Регистрация ----------

def test_register_requires_all_fields_and_nonempty_password(anon_client):
    anon_client.post('/register', data={'login': 'u', 'password': '', 'last_name': 'A',
                                        'first_name': 'B', 'middle_name': 'C'})
    assert _scalar("SELECT COUNT(*) FROM app_user WHERE login='u'") == 0
    anon_client.post('/register', data={'login': 'u', 'password': 'p', 'last_name': 'A',
                                        'first_name': 'B', 'middle_name': ''})
    assert _scalar("SELECT COUNT(*) FROM app_user WHERE login='u'") == 0
    anon_client.post('/register', data={'login': 'u', 'password': 'p', 'last_name': 'A',
                                        'first_name': 'B', 'middle_name': 'C'})
    assert _scalar("SELECT COUNT(*) FROM app_user WHERE login='u' AND role='user'") == 1
    assert _scalar("SELECT COUNT(*) FROM employee WHERE last_name='A' AND first_name='B'") == 1
    # дубликат логина
    anon_client.post('/register', data={'login': 'U', 'password': 'p', 'last_name': 'A',
                                        'first_name': 'B', 'middle_name': 'C'})
    assert _scalar("SELECT COUNT(*) FROM app_user") == 2  # admin + u


# ---------- Роль Пользователь ----------

def test_user_cannot_do_admin_writes(client):
    _seed_project_with_user(client)
    _login_user(client)
    client.post('/projects/create', data={'name': 'Новый', 'priority_id': '1'})
    assert _scalar("SELECT COUNT(*) FROM project WHERE name='Новый'") == 0
    client.post('/employees/create', data={'last_name': 'X', 'first_name': 'Y',
                                           'position_type_id': '1', 'status_id': '1'})
    assert _scalar("SELECT COUNT(*) FROM employee WHERE last_name='X'") == 0


def test_user_can_create_subtask_and_change_status(client):
    _seed_project_with_user(client)
    _login_user(client)
    client.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'Sub',
                                          'priority_id': '1', 'status_id': '1'})
    assert _scalar("SELECT COUNT(*) FROM subtask WHERE description='Sub'") == 1
    accepted = _status_id('Принята к исполнению')
    client.post('/tasks/1/status', data={'status_id': str(accepted)})
    assert _scalar("SELECT status_id FROM task WHERE id=1") == accepted


# ---------- Настройка назначения исполнителя ----------

def test_setting_controls_subtask_assignment(client):
    emp = _seed_project_with_user(client)
    # второй сотрудник в проекте
    client.post('/employees/create', data={'last_name': 'Второй', 'first_name': 'С',
                                           'position_type_id': '1', 'status_id': '1'})
    other = _scalar("SELECT id FROM employee WHERE last_name='Второй'")
    client.post('/projects/1/add_employee', data={'employee_id': str(other)})
    client.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'Sub1',
                                          'priority_id': '1', 'status_id': '1'})
    client.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'Sub2',
                                          'priority_id': '1', 'status_id': '1'})
    _login_user(client)
    # по умолчанию ON — можно назначить другого
    client.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'subtask',
                                                  'employee_id': str(other), 'share': '1.0'})
    assert _scalar("SELECT employee_id FROM task_assignment WHERE task_kind='subtask' AND task_id=1 AND is_deleted=0") == other
    # выключаем настройку (admin)
    client.get('/logout')
    client.post('/login', data={'login': 'admin', 'password': '12345'})
    client.post('/settings', data={})
    client.get('/logout')
    client.post('/login', data={'login': 'user1', 'password': 'pw'})
    # на второй (бесхозной) подзадаче другого назначить нельзя
    client.post('/task_assignments/create', data={'task_id': '2', 'task_kind': 'subtask',
                                                  'employee_id': str(other), 'share': '1.0'})
    assert _scalar("SELECT COUNT(*) FROM task_assignment WHERE task_kind='subtask' AND task_id=2 AND is_deleted=0") == 0
    # себя — можно
    client.post('/task_assignments/create', data={'task_id': '2', 'task_kind': 'subtask',
                                                  'employee_id': str(emp), 'share': '1.0'})
    assert _scalar("SELECT employee_id FROM task_assignment WHERE task_kind='subtask' AND task_id=2 AND is_deleted=0") == emp
    # «не назначен» — снятие
    client.post('/task_assignments/create', data={'task_id': '2', 'task_kind': 'subtask',
                                                  'employee_id': '', 'share': '1.0'})
    assert _scalar("SELECT COUNT(*) FROM task_assignment WHERE task_kind='subtask' AND task_id=2 AND is_deleted=0") == 0


# ---------- Чат ----------

def test_chat_read_all_write_logged_in(anon_client):
    assert anon_client.get('/chat').status_code == 200
    r = anon_client.post('/chat/post', data={'text': 'привет'})
    assert r.status_code == 302 and '/login' in r.headers['Location']
    assert _scalar("SELECT COUNT(*) FROM chat_message") == 0
    anon_client.post('/login', data={'login': 'admin', 'password': '12345'})
    anon_client.post('/chat/post', data={'text': 'привет'})
    assert _scalar("SELECT COUNT(*) FROM chat_message") == 1


# ---------- Аудит и автор назначения ----------

def test_audit_logged_and_restricted(client):
    client.post('/events/create', data={'description': 'E'})
    assert _scalar("SELECT COUNT(*) FROM audit_log WHERE action='event_create'") >= 1
    client.post('/register', data={'login': 'user1', 'password': 'pw', 'last_name': 'И',
                                   'first_name': 'И', 'middle_name': 'И'})
    _login_user(client)
    assert client.get('/audit').status_code == 302


def test_assignment_records_author(client):
    _seed_project_with_user(client)
    admin_id = _scalar("SELECT id FROM app_user WHERE login='admin'")
    assert _scalar("SELECT assigned_by_user_id FROM task_assignment WHERE task_kind='task'") == admin_id
    html = client.get('/tasks/1').get_data(as_text=True)
    assert 'Назначил' in html and 'admin' in html


def test_owner_cannot_manage_subtask_assigned_to_other(client):
    emp = _seed_project_with_user(client)
    client.post('/employees/create', data={'last_name': 'Второй', 'first_name': 'С',
                                           'position_type_id': '1', 'status_id': '1'})
    other = _scalar("SELECT id FROM employee WHERE last_name='Второй'")
    client.post('/projects/1/add_employee', data={'employee_id': str(other)})
    client.post('/subtasks/create', data={'parent_task_id': '1', 'description': 'Owned',
                                          'priority_id': '1', 'status_id': str(_status_id('Новая'))})
    client.post('/task_assignments/create', data={'task_id': '1', 'task_kind': 'subtask',
                                                  'employee_id': str(other), 'share': '1.0'})
    _login_user(client)
    before = _scalar("SELECT status_id FROM subtask WHERE id=1")
    accepted = _status_id('Принята к исполнению')
    client.post('/subtasks/1/status', data={'status_id': str(accepted)})
    assert _scalar("SELECT status_id FROM subtask WHERE id=1") == before != accepted


def test_open_redirect_rejected(client):
    _seed_project_with_user(client)
    _login_user(client)
    accepted = _status_id('Принята к исполнению')
    r = client.post('/tasks/1/status', data={'status_id': str(accepted), 'next': '/\\evil.com'})
    assert r.status_code == 302
    assert 'evil.com' not in r.headers['Location']
