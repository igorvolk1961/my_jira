"""Детальные страницы."""

from app_core import (  # noqa: F401
    AUDIO_DIR,
    BASE_DIR,
    BASE_TEMPLATE,
    BytesIO,
    DATABASE_DIR,
    DEFAULT_DB_NAME,
    Flask,
    _comments_html,
    _covered_for_employee,
    _detail_page,
    _developer_type_id,
    _employee_effective_load,
    _employee_load_excluding,
    _employee_position_name,
    _entity_comments,
    _entity_project_id,
    _last_comment,
    _project_employee_options,
    _projected_load_after,
    _render_tables,
    _report_page,
    _reset_employee_stackholder_if_unlinked,
    _soft_delete_subtask_tree,
    _subtask_ancestors,
    app,
    backup_db,
    current_db_name,
    date,
    datetime,
    db_path_for,
    flash,
    fmt_timecode,
    get_db,
    html,
    init_db,
    json,
    jsonify,
    os,
    re,
    redirect,
    render_template_string,
    request,
    secure_filename,
    send_file,
    session,
    shutil,
    sqlite3,
    sync_stakeholder_for_employee,
    url_for,
)
from app_core import (  # noqa: F401
    _active_task_assignee,
    _user_can_manage_subtask,
    assigner_sql,
    current_user,
    is_admin,
    role_label,
    status_form,
)

#==================== ДЕТАЛЬНЫЕ СТРАНИЦЫ ====================

@app.route('/employees/<int:id>')
def employee_detail(id):
    db = get_db()
    emp = db.execute("""
        SELECT e.*, pt.name position_name, es.name status_name, es.is_available,
               u.role AS user_role, u.is_analyst AS user_analyst, u.login AS user_login
        FROM employee e
        JOIN position_type pt ON e.position_type_id=pt.id
        JOIN employee_status es ON e.status_id=es.id
        LEFT JOIN app_user u ON u.employee_id=e.id AND u.is_deleted=0
        WHERE e.id=? AND e.is_deleted=0
    """, (id,)).fetchone()
    if not emp:
        db.close()
        flash('Сотрудник не найден', 'error')
        return redirect(url_for('employees_list'))
    load = _employee_effective_load(db, id)
    covered = _covered_for_employee(db, id)
    tasks = db.execute("""
        SELECT ta.share, t.id, t.description, t.deadline, pr.name prio, ts.name st, ts.color color,
               p.name pname, pst.name stype
        FROM task_assignment ta
        JOIN task t ON ta.task_id=t.id
        JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        LEFT JOIN project p ON p.id=COALESCE(ps.project_id, (SELECT project_id FROM requirement WHERE id=t.requirement_id))
        WHERE ta.employee_id=? AND ta.task_kind='task' AND ta.is_deleted=0 AND t.is_deleted=0
        ORDER BY t.id DESC
    """, (id,)).fetchall()
    tasks = [t for t in tasks if ('task', t['id']) not in covered]
    subtasks = db.execute("""
        SELECT ta.share, s.id, s.description, s.deadline, pr.name prio, ts.name st, ts.color color, t.description parent
        FROM task_assignment ta
        JOIN subtask s ON ta.task_id=s.id
        JOIN task t ON s.parent_task_id=t.id
        JOIN priority pr ON s.priority_id=pr.id
        JOIN task_status ts ON s.status_id=ts.id
        WHERE ta.employee_id=? AND ta.task_kind='subtask' AND ta.is_deleted=0 AND s.is_deleted=0
        ORDER BY s.id DESC
    """, (id,)).fetchall()
    subtasks = [s for s in subtasks if ('subtask', s['id']) not in covered]
    db.close()
    info = [
        ('Сотрудник', f"{emp['last_name']} {emp['first_name']} {emp['middle_name'] or ''}"),
        ('Должность', html.escape(emp['position_name'])),
        ('Статус', f'<span class="badge" style="background: {"#27ae60" if emp["is_available"] else "#e74c3c"}">{html.escape(emp["status_name"])}</span>'),
        ('Роль', role_label(emp['user_role'], emp['user_analyst']) if emp['user_role'] else '—'),
        ('Логин', html.escape(emp['user_login']) if emp['user_login'] else '—'),
        ('Подчинённые', f"{emp['subordinates_total']} (доступно: {emp['subordinates_available']})"),
        ('Загрузка', f'{round(load * 100)}%'),
    ]
    rows_t = [[
        f'<a href="{url_for("task_detail", id=t["id"])}">#{t["id"]}</a>',
        t['pname'] or '-', t['stype'] or '-', t['description'][:50], t['prio'],
        t['deadline'] or '-',
        f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{t["st"]}</span>',
        f'{round(t["share"] * 100)}%',
    ] for t in tasks]
    rows_s = [[
        f'<a href="{url_for("subtask_detail", id=s["id"])}">#{s["id"]}</a>',
        s['parent'][:50], s['description'][:50], s['prio'], s['deadline'] or '-',
        f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["st"]}</span>',
        f'{round(s["share"] * 100)}%',
    ] for s in subtasks]
    return _detail_page('Сотрудник: ' + emp['last_name'] + ' ' + emp['first_name'], info, [
        {'title': 'Задачи, где сотрудник назначен', 'headers': ['ID', 'Проект', 'Этап', 'Задача', 'Приоритет', 'Срок', 'Статус', 'Доля'], 'rows': rows_t},
        {'title': 'Подзадачи, где сотрудник назначен', 'headers': ['ID', 'Родительская задача', 'Описание', 'Приоритет', 'Срок', 'Статус', 'Доля'], 'rows': rows_s},
    ])

@app.route('/tasks/<int:id>')
def task_detail(id):
    db = get_db()
    t = db.execute("""
        SELECT t.*, pr.name prio, ts.name st, ts.color color, p.name pname, p.id pid, pst.name stype, ps.id stage_id,
               r.id req_id, r.description req_desc, tt.name type_name
        FROM task t
        JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        LEFT JOIN requirement r ON t.requirement_id=r.id
        LEFT JOIN task_type tt ON t.task_type_id=tt.id
        LEFT JOIN project p ON p.id=COALESCE(ps.project_id, (SELECT project_id FROM requirement WHERE id=t.requirement_id))
        WHERE t.id=? AND t.is_deleted=0
    """, (id,)).fetchone()
    if not t:
        db.close()
        flash('Задача не найдена', 'error')
        return redirect(url_for('tasks_list'))
    executors = db.execute(f"""
        SELECT e.id eid, e.last_name, e.first_name, pt.name pos, ta.share,
               {assigner_sql('au', 'ap')} assigner,
               ta.assigned_at assigned_at
        FROM task_assignment ta JOIN employee e ON ta.employee_id=e.id
        LEFT JOIN position_type pt ON e.position_type_id=pt.id
        LEFT JOIN app_user ap ON ta.assigned_by_user_id=ap.id
        LEFT JOIN employee au ON ap.employee_id=au.id
        WHERE ta.task_id=? AND ta.task_kind='task' AND ta.is_deleted=0
    """, (id,)).fetchall()
    statuses = db.execute("SELECT id, name FROM task_status WHERE is_deleted=0 ORDER BY id").fetchall()
    subtasks = db.execute("""
        SELECT s.id, s.description, s.deadline, pr.name prio, ts.name st, ts.color color
        FROM subtask s JOIN priority pr ON s.priority_id=pr.id
        JOIN task_status ts ON s.status_id=ts.id
        WHERE s.parent_task_id=? AND s.is_deleted=0 ORDER BY s.id
    """, (id,)).fetchall()
    comments = db.execute("SELECT * FROM comment WHERE entity_type='task' AND entity_id=? AND is_deleted=0 ORDER BY created_at DESC, id DESC", (id,)).fetchall()
    _u = current_user()
    can_status = bool(_u and (is_admin() or _active_task_assignee(db, id, _u['employee_id'])))
    db.close()
    info = [
        ('Задача', f'#{id}'),
        ('Проект', f'<a href="{url_for("project_detail", id=t["pid"])}">{t["pname"]}</a>' if t['pid'] else '-'),
        ('Этап', f'<a href="{url_for("project_stage_detail", id=t["stage_id"])}">{t["stype"]}</a>' if t['stage_id'] else '-'),
        ('Описание', t['description']),
        ('Тип', t['type_name'] or '-'),
        ('Приоритет', t['prio']),
        ('Срок', t['deadline'] or '-'),
        ('Статус', f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{t["st"]}</span>'),
        ('Требование', f'<a href="{url_for("requirement_detail", id=t["req_id"])}">{t["req_desc"]}</a>' if t['req_id'] else '-'),
    ]
    rows_exec = [[f'<a href="{url_for("employee_detail", id=e["eid"])}">{e["last_name"]} {e["first_name"]}</a>',
                  e['pos'] or '-', f'{round(e["share"] * 100)}%',
                  f'{html.escape(e["assigner"] or "—")} <span class="muted">({e["assigned_at"] or "—"})</span>'] for e in executors]
    rows_sub = [[f'<a href="{url_for("subtask_detail", id=s["id"])}">#{s["id"]}</a>', s['description'][:60], s['prio'],
                 s['deadline'] or '-', f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["st"]}</span>'] for s in subtasks]
    add_comment = f'<a href="{url_for("comment_create", entity_type="task", entity_id=id)}" class="btn btn-success">+ Комментарий</a>'
    add_subtask = f'<a href="{url_for("subtask_create", parent_task_id=id)}" class="btn btn-success">+ Подзадача</a>'
    rows_c = [[c['created_at'], c['author'] or '-', c['text'],
               f'<a href="{url_for("comment_delete", id=c["id"])}" class="btn btn-danger" onclick="return confirm(\'Удалить?\')">Удалить</a>'] for c in comments]
    add_req = f'<a href="{url_for("requirement_create", project_id=t["pid"], task_id=id)}" class="btn btn-success">+ Требование</a>' if t['pid'] else ''
    add_assign = f'<a href="{url_for("task_assignment_create", task_id=id, task_kind="task", origin=t["pid"])}" class="btn btn-warning">Назначить</a>' if t['pid'] else ''
    status_html = ''
    if can_status:
        status_html = status_form('task_status_change', id, statuses, t['status_id'])
    return _detail_page(f'Задача #{id}', info, tables=[
        {'title': 'Кто выполняет', 'headers': ['Сотрудник', 'Должность', 'Доля', 'Назначил'], 'rows': rows_exec},
        {'title': 'Подзадачи ' + add_subtask, 'headers': ['ID', 'Описание', 'Приоритет', 'Срок', 'Статус'], 'rows': rows_sub},
        {'title': 'Комментарии ' + add_comment, 'headers': ['Дата', 'Автор', 'Текст', 'Действия'], 'rows': rows_c},
    ], actions=add_req + ' ' + add_assign + ' ' + status_html)

@app.route('/subtasks/<int:id>')
def subtask_detail(id):
    db = get_db()
    s = db.execute("""
        SELECT s.*, t.description parent_desc, t.id parent_id, pr.name prio, ts.name st, ts.color color
        FROM subtask s JOIN task t ON s.parent_task_id=t.id
        JOIN priority pr ON s.priority_id=pr.id
        JOIN task_status ts ON s.status_id=ts.id
        WHERE s.id=? AND s.is_deleted=0
    """, (id,)).fetchone()
    if not s:
        db.close()
        flash('Подзадача не найдена', 'error')
        return redirect(url_for('subtasks_list'))
    executors = db.execute(f"""
        SELECT e.id eid, e.last_name, e.first_name, pt.name pos, ta.share,
               {assigner_sql('au', 'ap')} assigner,
               ta.assigned_at assigned_at
        FROM task_assignment ta JOIN employee e ON ta.employee_id=e.id
        LEFT JOIN position_type pt ON e.position_type_id=pt.id
        LEFT JOIN app_user ap ON ta.assigned_by_user_id=ap.id
        LEFT JOIN employee au ON ap.employee_id=au.id
        WHERE ta.task_id=? AND ta.task_kind='subtask' AND ta.is_deleted=0
    """, (id,)).fetchall()
    statuses = db.execute("SELECT id, name FROM task_status WHERE is_deleted=0 ORDER BY id").fetchall()
    comments = db.execute("SELECT * FROM comment WHERE entity_type='subtask' AND entity_id=? AND is_deleted=0 ORDER BY created_at DESC, id DESC", (id,)).fetchall()
    pid = _entity_project_id(db, 'subtask', id)
    _u = current_user()
    can_status = bool(_u and (is_admin() or _user_can_manage_subtask(db, _u['employee_id'], id)))
    db.close()
    info = [
        ('Подзадача', f'#{id}'),
        ('Родительская задача', f'<a href="{url_for("task_detail", id=s["parent_id"])}">#{s["parent_id"]} {s["parent_desc"][:40]}</a>'),
        ('Описание', s['description']),
        ('Приоритет', s['prio']),
        ('Срок', s['deadline'] or '-'),
        ('Статус', f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["st"]}</span>'),
    ]
    rows_exec = [[f'<a href="{url_for("employee_detail", id=e["eid"])}">{e["last_name"]} {e["first_name"]}</a>',
                  e['pos'] or '-', f'{round(e["share"] * 100)}%',
                  f'{html.escape(e["assigner"] or "—")} <span class="muted">({e["assigned_at"] or "—"})</span>'] for e in executors]
    add_comment = f'<a href="{url_for("comment_create", entity_type="subtask", entity_id=id)}" class="btn btn-success">+ Комментарий</a>'
    add_subtask = f'<a href="{url_for("subtask_create", parent_subtask_id=id)}" class="btn btn-success">+ Подзадача</a>'
    add_assign = f'<a href="{url_for("task_assignment_create", task_id=id, task_kind="subtask", origin=pid)}" class="btn btn-warning">Назначить</a>' if pid else ''
    rows_c = [[c['created_at'], c['author'] or '-', c['text'],
               f'<a href="{url_for("comment_delete", id=c["id"])}" class="btn btn-danger" onclick="return confirm(\'Удалить?\')">Удалить</a>'] for c in comments]
    status_html = ''
    if can_status:
        status_html = status_form('subtask_status_change', id, statuses, s['status_id'])
    return _detail_page(f'Подзадача #{id}', info, [
        {'title': 'Кто выполняет', 'headers': ['Сотрудник', 'Должность', 'Доля', 'Назначил'], 'rows': rows_exec},
        {'title': 'Вложенные подзадачи ' + add_subtask, 'headers': ['Действия'], 'rows': []},
        {'title': 'Комментарии ' + add_comment, 'headers': ['Дата', 'Автор', 'Текст', 'Действия'], 'rows': rows_c},
    ], actions=add_assign + ' ' + status_html)

@app.route('/stakeholders/<int:id>')
def stakeholder_detail(id):
    db = get_db()
    sh = db.execute("""
        SELECT s.*, st.name type_name, st.influence_priority inf, st.interest_priority ints
        FROM stakeholder s JOIN stakeholder_type st ON s.type_id=st.id
        WHERE s.id=? AND s.is_deleted=0
    """, (id,)).fetchone()
    if not sh:
        db.close()
        flash('Стейкхолдер не найден', 'error')
        return redirect(url_for('stakeholders_list'))
    projects = db.execute("""
        SELECT p.id, p.name, pr.name prio, p.deadline
        FROM project p JOIN priority pr ON p.priority_id=pr.id
        WHERE p.main_stakeholder_id=? AND p.is_deleted=0
    """, (id,)).fetchall()
    reqs = db.execute("""
        SELECT r.id, r.description, p.name pname, rt.name type_name, pr.name prio
        FROM requirement r JOIN project p ON r.project_id=p.id
        JOIN requirement_type rt ON r.requirement_type_id=rt.id
        JOIN priority pr ON r.priority_id=pr.id
        WHERE r.stakeholder_id=? AND r.is_deleted=0
    """, (id,)).fetchall()
    interviews = db.execute("""
        SELECT INTERV.* FROM interview INTERV
        WHERE INTERV.stakeholder_id=? AND INTERV.is_deleted=0
        ORDER BY INTERV.scheduled_at DESC
    """, (id,)).fetchall()
    db.close()
    info = [
        ('Стейкхолдер', f"{sh['last_name']} {sh['first_name']}"),
        ('Тип', sh['type_name']),
        ('Влияние / Интерес', f"{sh['inf']}/5, {sh['ints']}/5"),
        ('Должность', sh['position'] or '-'),
        ('Приоритет', sh['priority']),
    ]
    rows_proj = [[f'<a href="{url_for("project_detail", id=p["id"])}">{p["name"]}</a>', p['prio'], p['deadline'] or '-'] for p in projects]
    rows_req = [[f'<a href="{url_for("requirement_detail", id=r["id"])}">#{r["id"]}</a>', r['description'][:60], r['pname'], r['type_name'], r['prio']] for r in reqs]
    rows_int = [[f'<a href="{url_for("interview_detail", id=i["id"])}">#{i["id"]}</a>', i['scheduled_at'] or '-'] for i in interviews]
    add_interview = f'<a href="{url_for("interview_create", stakeholder_id=id)}" class="btn btn-success">+ Назначить интервью</a>'
    return _detail_page('Стейкхолдер: ' + sh['last_name'] + ' ' + sh['first_name'], info, [
        {'title': 'Проекты (главный стейкхолдер)', 'headers': ['Проект', 'Приоритет', 'Срок'], 'rows': rows_proj},
        {'title': 'Требования стейкхолдера', 'headers': ['ID', 'Описание', 'Проект', 'Тип', 'Приоритет'], 'rows': rows_req},
        {'title': 'Интервью стейкхолдера ' + add_interview, 'headers': ['ID', 'Дата-время'], 'rows': rows_int},
    ])

@app.route('/requirements/<int:id>')
def requirement_detail(id):
    db = get_db()
    r = db.execute("""
        SELECT r.*, p.name pname, rt.name type_name, pr.name prio, s.last_name, s.first_name
        FROM requirement r JOIN project p ON r.project_id=p.id
        JOIN requirement_type rt ON r.requirement_type_id=rt.id
        JOIN priority pr ON r.priority_id=pr.id
        LEFT JOIN stakeholder s ON r.stakeholder_id=s.id
        WHERE r.id=? AND r.is_deleted=0
    """, (id,)).fetchone()
    if not r:
        db.close()
        flash('Требование не найдено', 'error')
        return redirect(url_for('requirements_list'))
    tasks = db.execute("""
        SELECT t.id, t.description, t.deadline, pr.name prio, ts.name st, ts.color color, pst.name stype
        FROM task t JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        WHERE t.requirement_id=? AND t.is_deleted=0
    """, (id,)).fetchall()
    db.close()
    info = [
        ('Требование', f'#{id}'),
        ('Проект', r['pname']),
        ('Тип', r['type_name']),
        ('Приоритет', r['prio']),
        ('Стейкхолдер', f"{r['last_name'] or '-'} {r['first_name'] or ''}"),
        ('Описание', r['description']),
        ('Критерий проверки', r['acceptance_criteria'] or '-'),
    ]
    rows = [[f'<a href="{url_for("task_detail", id=t["id"])}">#{t["id"]}</a>', t['description'][:60], t['stype'] or '-',
             t['prio'], t['deadline'] or '-', f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{t["st"]}</span>'] for t in tasks]
    return _detail_page(f'Требование #{id}', info, [
        {'title': 'Задачи, реализующие требование', 'headers': ['ID', 'Описание', 'Этап', 'Приоритет', 'Срок', 'Статус'], 'rows': rows},
    ])

@app.route('/project_stages/<int:id>')
def project_stage_detail(id):
    db = get_db()
    st = db.execute("""
        SELECT ps.*, p.name pname, pst.name type_name, pss.name status_name, pss.color
        FROM project_stage ps
        JOIN project p ON ps.project_id=p.id
        JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE ps.id=? AND ps.is_deleted=0
    """, (id,)).fetchone()
    if not st:
        db.close()
        flash('Этап не найден', 'error')
        return redirect(url_for('project_stages_list'))
    tasks = db.execute("""
        SELECT t.id, t.description, t.deadline, pr.name prio, ts.name st, ts.color color,
               (SELECT GROUP_CONCAT(e.last_name || ' ' || e.first_name, ', ')
                FROM task_assignment ta JOIN employee e ON ta.employee_id=e.id
                WHERE ta.task_id=t.id AND ta.task_kind='task' AND ta.is_deleted=0) executors
        FROM task t JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        WHERE t.stage_id=? AND t.is_deleted=0
        ORDER BY t.id
    """, (id,)).fetchall()
    db.close()
    info = [
        ('Этап', st['type_name']),
        ('Проект', f'<a href="{url_for("project_detail", id=st["project_id"])}">{st["pname"]}</a>'),
        ('Статус', f'<span class="badge" style="background: {st["color"] or "#95a5a6"}">{st["status_name"]}</span>'),
        ('Плановая дата', st['planned_end'] or '-'),
    ]
    rows = [[f'<a href="{url_for("task_detail", id=t["id"])}">#{t["id"]}</a>', t['description'][:60], t['prio'],
             t['deadline'] or '-', f'<span class="badge" style="background: {t["color"] or "#95a5a6"}">{t["st"]}</span>',
             t['executors'] or 'не назначено'] for t in tasks]
    add_task = f'<a href="{url_for("task_create", stage_id=id, origin=st["project_id"])}" class="btn btn-success">+ Задача</a>'
    return _detail_page('Этап: ' + st['type_name'], info, [
        {'title': 'Задачи этапа ' + add_task, 'headers': ['ID', 'Описание', 'Приоритет', 'Срок', 'Статус', 'Исполнители'], 'rows': rows},
    ])

@app.route('/task_assignments/<int:id>')
def task_assignment_detail(id):
    db = get_db()
    a = db.execute("""
        SELECT ta.*, e.last_name, e.first_name, pt.name pos,
               CASE WHEN ta.task_kind='task' THEN (SELECT description FROM task WHERE id=ta.task_id)
                    ELSE (SELECT description FROM subtask WHERE id=ta.task_id) END task_desc
        FROM task_assignment ta JOIN employee e ON ta.employee_id=e.id
        LEFT JOIN position_type pt ON e.position_type_id=pt.id
        WHERE ta.id=? AND ta.is_deleted=0
    """, (id,)).fetchone()
    if not a:
        db.close()
        flash('Назначение не найдено', 'error')
        return redirect(url_for('task_assignments_list'))
    db.close()
    info = [
        ('Назначение', f'#{id}'),
        ('Тип', a['task_kind']),
        ('Задача', a['task_desc'] or '-'),
        ('Сотрудник', a['last_name'] + ' ' + a['first_name']),
        ('Должность', a['pos'] or '-'),
        ('Доля', f'{round(a["share"] * 100)}%'),
    ]
    return _detail_page(f'Назначение #{id}', info)

@app.route('/events/<int:id>')
def event_detail(id):
    db = get_db()
    e = db.execute("SELECT * FROM event WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not e:
        db.close()
        flash('Событие не найдено', 'error')
        return redirect(url_for('events_list'))
    db.close()
    info = [
        ('Событие', f'#{id}'),
        ('Дата', e['occurred_at']),
        ('Описание', e['description']),
        ('Решение', e['decision'] or '-'),
    ]
    return _detail_page(f'Событие #{id}', info)


