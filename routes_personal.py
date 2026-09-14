"""Разделы «Мои задачи» (пользователь) и «Задачи» (администратор)."""

from app_core import (  # noqa: F401
    BASE_TEMPLATE,
    _managed_subtask_ids,
    _project_employee_options,
    app,
    assigner_sql,
    current_user,
    date,
    get_db,
    html,
    login_required,
    redirect,
    render_template_string,
    request,
    status_form,
    url_for,
)

_TASK_TMPL = """
    SELECT 'task' AS kind, t.id AS id, t.description AS description,
           COALESCE(ps.project_id, r.project_id) AS project_id, p.name AS project_name,
           pr.name AS priority_name, t.deadline AS deadline,
           ts.id AS status_id, ts.name AS status_name, ts.color AS status_color,
           (SELECT GROUP_CONCAT(TRIM(e3.last_name || ' ' || e3.first_name), ', ')
              FROM task_assignment ta3 JOIN employee e3 ON ta3.employee_id = e3.id
             WHERE ta3.task_id = t.id AND ta3.task_kind = 'task' AND ta3.is_deleted = 0) AS executors,
           (SELECT {assigner}
              FROM task_assignment ta2 LEFT JOIN app_user u2 ON ta2.assigned_by_user_id = u2.id
              LEFT JOIN employee e2 ON u2.employee_id = e2.id
             WHERE ta2.task_id = t.id AND ta2.task_kind = 'task' AND ta2.is_deleted = 0
             ORDER BY ta2.assigned_at DESC, ta2.id DESC LIMIT 1) AS assigner
    FROM task t
    JOIN priority pr ON t.priority_id = pr.id
    JOIN task_status ts ON t.status_id = ts.id
    LEFT JOIN project_stage ps ON t.stage_id = ps.id
    LEFT JOIN requirement r ON t.requirement_id = r.id
    LEFT JOIN project p ON p.id = COALESCE(ps.project_id, r.project_id)
    WHERE t.is_deleted = 0 {extra}
"""

_SUBTASK_TMPL = """
    SELECT 'subtask' AS kind, s.id AS id, s.description AS description,
           COALESCE(ps.project_id, r.project_id) AS project_id, p.name AS project_name,
           pr.name AS priority_name, s.deadline AS deadline,
           ts.id AS status_id, ts.name AS status_name, ts.color AS status_color,
           (SELECT GROUP_CONCAT(TRIM(e3.last_name || ' ' || e3.first_name), ', ')
              FROM task_assignment ta3 JOIN employee e3 ON ta3.employee_id = e3.id
             WHERE ta3.task_id = s.id AND ta3.task_kind = 'subtask' AND ta3.is_deleted = 0) AS executors,
           (SELECT {assigner}
              FROM task_assignment ta2 LEFT JOIN app_user u2 ON ta2.assigned_by_user_id = u2.id
              LEFT JOIN employee e2 ON u2.employee_id = e2.id
             WHERE ta2.task_id = s.id AND ta2.task_kind = 'subtask' AND ta2.is_deleted = 0
             ORDER BY ta2.assigned_at DESC, ta2.id DESC LIMIT 1) AS assigner
    FROM subtask s
    JOIN task t ON s.parent_task_id = t.id
    JOIN priority pr ON s.priority_id = pr.id
    JOIN task_status ts ON s.status_id = ts.id
    LEFT JOIN project_stage ps ON t.stage_id = ps.id
    LEFT JOIN requirement r ON t.requirement_id = r.id
    LEFT JOIN project p ON p.id = COALESCE(ps.project_id, r.project_id)
    WHERE s.is_deleted = 0 {extra}
"""

_DONE_STATUSES = "('Выполнена', 'Отменена')"
_ACCEPTED_STATUSES = "('Принята к исполнению', 'Выполнена', 'Отменена')"


def _task_sql(extra=''):
    return _TASK_TMPL.format(assigner=assigner_sql('e2', 'u2'), extra=extra)


def _subtask_sql(extra=''):
    return _SUBTASK_TMPL.format(assigner=assigner_sql('e2', 'u2'), extra=extra)


def _tab_extras(alias):
    return {
        'unassigned': (f"AND NOT EXISTS (SELECT 1 FROM task_assignment ta "
                       f"WHERE ta.task_id={alias}.id AND ta.task_kind={{kind}} AND ta.is_deleted=0)"),
        'not_accepted': (f"AND EXISTS (SELECT 1 FROM task_assignment ta "
                         f"WHERE ta.task_id={alias}.id AND ta.task_kind={{kind}} AND ta.is_deleted=0) "
                         f"AND {alias}.status_id NOT IN (SELECT id FROM task_status WHERE name IN {_ACCEPTED_STATUSES})"),
        'overdue': (f"AND {alias}.deadline IS NOT NULL AND {alias}.deadline < date('now') "
                    f"AND {alias}.status_id NOT IN (SELECT id FROM task_status WHERE name IN {_DONE_STATUSES})"),
    }


def _item_row(item, statuses, extra_action, back):
    link_endpoint = 'task_detail' if item['kind'] == 'task' else 'subtask_detail'
    kind_label = 'Задача' if item['kind'] == 'task' else 'Подзадача'
    deadline = item['deadline'] or '-'
    overdue = False
    if item['deadline']:
        overdue = str(item['deadline']) < date.today().isoformat() and item['status_name'] not in ('Выполнена', 'Отменена')
    deadline_style = ' style="color:#e74c3c; font-weight:bold;"' if overdue else ''
    endpoint = 'task_status_change' if item['kind'] == 'task' else 'subtask_status_change'
    action = extra_action or status_form(endpoint, item['id'], statuses, item['status_id'], back=back)
    return f'''<tr>
        <td>{kind_label}</td>
        <td><a href="{url_for(link_endpoint, id=item['id'])}">#{item['id']}</a> {html.escape((item['description'] or '')[:50])}</td>
        <td>{html.escape(item['project_name'] or '—')}</td>
        <td>{html.escape(item['executors'] or '—')}</td>
        <td>{html.escape(item['assigner'] or '—')}</td>
        <td{deadline_style}>{deadline}</td>
        <td><span class="badge" style="background: {item['status_color'] or '#95a5a6'}">{html.escape(item['status_name'])}</span></td>
        <td>{action}</td>
    </tr>'''


def _render_table(items, statuses, back, extra_action=None):
    body = ''.join([_item_row(it, statuses, extra_action(it) if extra_action else None, back) for it in items])
    if not body:
        body = '<tr><td colspan="8" class="muted">Записей нет</td></tr>'
    return body


@app.route('/my_tasks')
@login_required
def my_tasks():
    user = current_user()
    db = get_db()
    statuses = db.execute("SELECT id, name FROM task_status WHERE is_deleted=0 ORDER BY id").fetchall()
    items = []
    if user and user['employee_id']:
        emp = user['employee_id']
        assigned = {(r['task_id'], r['task_kind']) for r in db.execute(
            "SELECT task_id, task_kind FROM task_assignment WHERE employee_id=? AND is_deleted=0", (emp,))}
        managed = _managed_subtask_ids(db, emp)
        for kind, sql in (('task', _task_sql()), ('subtask', _subtask_sql())):
            for r in db.execute(sql):
                row = dict(r)
                if (row['id'], kind) in assigned:
                    items.append(row)
                elif kind == 'subtask' and not row['executors'] and row['id'] in managed:
                    items.append(row)
    groups = {}
    for it in items:
        key = (it['project_id'], it['project_name'] or 'Без проекта')
        groups.setdefault(key, []).append(it)
    db.close()

    blocks = ''
    for (pid, pname), rows in sorted(groups.items(), key=lambda kv: str(kv[0][1])):
        body = _render_table(rows, statuses, url_for('my_tasks'))
        title = f'<a href="{url_for("project_detail", id=pid)}">{html.escape(pname)}</a>' if pid else html.escape(pname)
        blocks += f'''
        <div class="card">
            <h2>{title}</h2>
            <table>
                <thead><tr><th>Тип</th><th>Объект</th><th>Проект</th><th>Исполнители</th><th>Назначил</th><th>Срок</th><th>Статус</th><th>Изменить статус</th></tr></thead>
                <tbody>{body}</tbody>
            </table>
        </div>'''
    if not blocks:
        blocks = '<div class="card"><p class="muted">Назначенных задач нет</p></div>'
    return render_template_string(BASE_TEMPLATE, title='Мои задачи', content=blocks)


@app.route('/tasks_admin')
def admin_tasks():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if user['role'] != 'admin':
        return redirect(url_for('my_tasks'))

    tab = request.args.get('tab') or 'unassigned'
    if tab not in ('unassigned', 'not_accepted', 'overdue'):
        tab = 'unassigned'

    db = get_db()
    statuses = db.execute("SELECT id, name FROM task_status WHERE is_deleted=0 ORDER BY id").fetchall()
    selected = []
    for kind, builder, alias in (('task', _task_sql, 't'), ('subtask', _subtask_sql, 's')):
        extra = _tab_extras(alias)[tab].format(kind="'%s'" % kind)
        selected.extend(dict(r) for r in db.execute(builder(extra)).fetchall())
    proj_emp = _project_employee_options(db)
    db.close()

    def assign_form(it):
        pid = it['project_id']
        if not pid or not proj_emp.get(pid):
            return '<span class="muted">нет команды проекта</span>'
        default_share = '1.0' if it['kind'] == 'subtask' else '0.5'
        return f'''<form method="POST" action="{url_for('task_assignment_create')}" style="display:flex; gap:6px; align-items:center; margin:0; flex-wrap:wrap;">
            <input type="hidden" name="task_kind" value="{it['kind']}">
            <input type="hidden" name="task_id" value="{it['id']}">
            <input type="hidden" name="next" value="{url_for('admin_tasks', tab=tab)}">
            <select name="employee_id" required>{proj_emp[pid]}</select>
            <input type="number" name="share" step="0.1" min="0" max="1" value="{default_share}" style="width:80px;" required>
            <button type="submit" class="btn btn-warning" style="margin:0;">Назначить</button>
        </form>'''

    body = _render_table(selected, statuses, url_for('admin_tasks', tab=tab),
                         extra_action=assign_form if tab == 'unassigned' else None)

    def tab_link(key, label):
        active = 'btn-success' if tab == key else 'btn-primary'
        return f'<a href="{url_for("admin_tasks", tab=key)}" class="btn {active}">{label}</a>'

    content = f'''
    <div class="card">
        <h2>Задачи</h2>
        <div style="margin-bottom:12px;">
            {tab_link('unassigned', 'Не назначенные')}
            {tab_link('not_accepted', 'Не принятые к исполнению')}
            {tab_link('overdue', 'Просроченные')}
        </div>
        <table>
            <thead><tr><th>Тип</th><th>Объект</th><th>Проект</th><th>Исполнители</th><th>Назначил</th><th>Срок</th><th>Статус</th><th>Действия</th></tr></thead>
            <tbody>{body}</tbody>
        </table>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Задачи', content=content)
