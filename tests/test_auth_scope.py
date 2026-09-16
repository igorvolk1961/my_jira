"""Аутентификация, авторизация, аудит, чат, автор назначения."""

import os
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


def _exec(sql, params=()):
    con = sqlite3.connect(main.db_path_for(TEST_DB))
    try:
        con.execute(sql, params)
        con.commit()
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


def test_employee_delete_allows_others_but_not_self(client):
    admin_emp = _scalar("SELECT employee_id FROM app_user WHERE login='admin'")
    client.get(f'/employees/delete/{admin_emp}')
    assert _scalar("SELECT COUNT(*) FROM employee WHERE id=? AND is_deleted=0", (admin_emp,)) == 1

    client.post('/register', data={'login': 'u2', 'password': 'p', 'last_name': 'У',
                                   'first_name': 'У', 'middle_name': 'У'})
    emp = _scalar("SELECT employee_id FROM app_user WHERE login='u2'")
    client.get(f'/employees/delete/{emp}')
    assert _scalar("SELECT COUNT(*) FROM employee WHERE id=? AND is_deleted=0", (emp,)) == 0
    assert _scalar("SELECT COUNT(*) FROM app_user WHERE login='u2' AND is_deleted=0") == 0
    other = main.app.test_client()
    other.post('/login', data={'login': 'u2', 'password': 'p'})
    assert other.get('/my_tasks').status_code == 302


def test_employee_role_change_by_admin_not_self_and_visible_to_all(client):
    _seed_project_with_user(client)
    emp = _scalar("SELECT employee_id FROM app_user WHERE login='user1'")
    client.post(f'/employees/role/{emp}', data={'role': 'admin'})
    assert _scalar("SELECT role FROM app_user WHERE login='user1'") == 'admin'
    # свою роль менять нельзя
    admin_emp = _scalar("SELECT employee_id FROM app_user WHERE login='admin'")
    client.post(f'/employees/role/{admin_emp}', data={'role': 'user'})
    assert _scalar("SELECT role FROM app_user WHERE login='admin'") == 'admin'
    # роль отображается в списке (для всех ролей)
    html = client.get('/employees').get_data(as_text=True)
    assert 'Роль' in html and 'администратор' in html


def test_role_change_keeps_non_analyst_position(client):
    """Смена базовой роли не должна перетирать должность сотрудника."""
    _seed_project_with_user(client)
    emp = _scalar("SELECT employee_id FROM app_user WHERE login='user1'")
    arch = _scalar("SELECT id FROM position_type WHERE name='Архитектор'")
    _exec("UPDATE employee SET position_type_id=? WHERE id=?", (arch, emp))
    client.post(f'/employees/role/{emp}', data={'role': 'admin'})
    assert _scalar("SELECT role FROM app_user WHERE login='user1'") == 'admin'
    assert _scalar("SELECT is_analyst FROM app_user WHERE login='user1'") == 0
    assert _scalar("SELECT position_type_id FROM employee WHERE id=?", (emp,)) == arch


def test_position_and_analyst_role_sync(client):
    """Должность «Системный аналитик» и роль синхронизируются в обе стороны."""
    _seed_project_with_user(client)
    emp = _scalar("SELECT employee_id FROM app_user WHERE login='user1'")
    analyst = _scalar("SELECT id FROM position_type WHERE name='Системный аналитик'")
    user_pos = _scalar("SELECT id FROM position_type WHERE name='Пользователь'")

    # должность → роль
    client.post(f'/employees/edit/{emp}', data={'last_name': 'Иванов', 'first_name': 'Иван',
                                                'position_type_id': str(analyst), 'status_id': '1'})
    assert _scalar("SELECT is_analyst FROM app_user WHERE login='user1'") == 1

    # снятие роли → должность «Пользователь»
    client.post(f'/employees/role/{emp}', data={'role': 'admin'})
    assert _scalar("SELECT is_analyst FROM app_user WHERE login='user1'") == 0
    assert _scalar("SELECT position_type_id FROM employee WHERE id=?", (emp,)) == user_pos

    # роль → должность (назначение)
    client.post(f'/employees/role/{emp}', data={'role': 'admin', 'is_analyst': '1'})
    assert _scalar("SELECT is_analyst FROM app_user WHERE login='user1'") == 1
    assert _scalar("SELECT position_type_id FROM employee WHERE id=?", (emp,)) == analyst


def test_employee_role_change_forbidden_for_user(client):
    _seed_project_with_user(client)
    client.post('/register', data={'login': 'u3', 'password': 'p', 'last_name': 'Т',
                                   'first_name': 'Т', 'middle_name': 'Т'})
    target = _scalar("SELECT employee_id FROM app_user WHERE login='u3'")
    _login_user(client)
    client.post(f'/employees/role/{target}', data={'role': 'admin'})
    assert _scalar("SELECT role FROM app_user WHERE login='u3'") == 'user'


def test_database_copy_preserves_data(client):
    _seed_project_with_user(client)
    client.post('/interviews/create', data={'stakeholder_id': '1', 'scheduled_at': '2026-01-01T10:00'})
    client.post('/interview_qa/create', data={'interview_id': '1', 'question': 'Вопрос?', 'answer': 'Ответ'})

    copy_name = 'pytest_copy.db'
    copy_path = main.db_path_for(copy_name)
    try:
        r = client.post('/database/copy', data={'source': main.DEFAULT_DB_NAME, 'name': 'pytest_copy',
                                                 'switch': '1'})
        assert r.status_code == 302
        assert os.path.exists(copy_path)
        con = sqlite3.connect(copy_path)
        try:
            # Копия не удаляет данные автоматически
            assert con.execute("SELECT COUNT(*) FROM project").fetchone()[0] >= 1
            assert con.execute("SELECT COUNT(*) FROM task").fetchone()[0] >= 1
            assert con.execute("SELECT COUNT(*) FROM app_user WHERE is_deleted=0").fetchone()[0] >= 2
            assert con.execute("SELECT COUNT(*) FROM interview").fetchone()[0] >= 1
            assert con.execute("SELECT COUNT(*) FROM interview_qa").fetchone()[0] >= 1
        finally:
            con.close()
    finally:
        for suffix in ('', '-wal', '-shm'):
            if os.path.exists(copy_path + suffix):
                os.remove(copy_path + suffix)
