"""Отчёты."""

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

#==================== ОТЧЁТЫ ====================


@app.route('/reports/projects')
def report_projects():
    db = get_db()
    proj_total = db.execute("SELECT COUNT(*) FROM project WHERE is_deleted=0").fetchone()[0]
    cost_total = db.execute("SELECT COALESCE(SUM(cost), 0) FROM project WHERE is_deleted=0").fetchone()[0]
    proj_budget = db.execute("SELECT COUNT(*) FROM project WHERE is_deleted=0 AND cost IS NOT NULL").fetchone()[0]
    prj_by_prio = db.execute("""
        SELECT pr.name, pr.weight, COUNT(p.id) cnt, COALESCE(SUM(p.cost), 0) cost
        FROM priority pr
        LEFT JOIN project p ON p.priority_id=pr.id AND p.is_deleted=0
        WHERE pr.is_deleted=0
        GROUP BY pr.id ORDER BY pr.weight
    """).fetchall()
    progress = db.execute("""
        SELECT p.id, p.name,
            (SELECT COUNT(*) FROM project_stage ps WHERE ps.project_id=p.id AND ps.is_deleted=0) stages,
            (SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
                WHERE ps.project_id=p.id AND ps.is_deleted=0 AND pss.name='Завершён') stages_done,
            (SELECT COUNT(*) FROM task t
                LEFT JOIN project_stage ps ON t.stage_id=ps.id
                LEFT JOIN requirement r ON t.requirement_id=r.id
                WHERE t.is_deleted=0 AND COALESCE(ps.project_id, r.project_id)=p.id) tasks,
            (SELECT COUNT(*) FROM task t
                LEFT JOIN project_stage ps ON t.stage_id=ps.id
                LEFT JOIN requirement r ON t.requirement_id=r.id
                JOIN task_status ts ON t.status_id=ts.id
                WHERE t.is_deleted=0 AND COALESCE(ps.project_id, r.project_id)=p.id
                  AND ts.name='Выполнена') tasks_done
        FROM project p WHERE p.is_deleted=0 ORDER BY p.name
    """).fetchall()
    db.close()
    avg_prio = (sum(p['weight'] * p['cnt'] for p in prj_by_prio) / proj_total) if proj_total else 0
    cards = [
        ('Всего проектов', proj_total, '#2c3e50'),
        ('Общая стоимость', f'{cost_total:,.0f}', '#2c3e50'),
        ('Проектов с бюджетом', proj_budget, '#2c3e50'),
        ('Средний приоритет', f'{avg_prio:.2f}' if proj_total else 0, '#2c3e50'),
    ]
    rows1 = [[p['name'], p['weight'], p['cnt'], f"{p['cost']:,.0f}"] for p in prj_by_prio]
    rows2 = []
    for p in progress:
        t_pct = round(p['tasks_done'] / p['tasks'] * 100) if p['tasks'] else 0
        s_pct = round(p['stages_done'] / p['stages'] * 100) if p['stages'] else 0
        rows2.append([f'<a href="{url_for("project_detail", id=p["id"])}">{p["name"]}</a>',
                      f"{p['stages_done']}/{p['stages']}",
                      f"{p['tasks_done']}/{p['tasks']}", f"{t_pct}%", f"{s_pct}%"])
    return _report_page('Отчёт: Проекты', cards, [
        {'title': 'Проекты по приоритетам', 'headers': ['Приоритет', 'Вес', 'Кол-во', 'Стоимость'], 'rows': rows1},
        {'title': 'Прогресс проектов', 'headers': ['Проект', 'Этапы (завершено/всего)', 'Задачи (выполнено/всего)', 'Прогресс по задачам', 'Прогресс по этапам'], 'rows': rows2},
    ])

@app.route('/reports/stakeholders')
def report_stakeholders():
    db = get_db()
    st_total = db.execute("SELECT COUNT(*) FROM stakeholder WHERE is_deleted=0").fetchone()[0]
    types = db.execute("""
        SELECT st.name, st.influence_priority inf, st.interest_priority ints, COUNT(s.id) cnt
        FROM stakeholder_type st
        LEFT JOIN stakeholder s ON s.type_id=st.id AND s.is_deleted=0
        WHERE st.is_deleted=0
        GROUP BY st.id ORDER BY st.influence_priority DESC, st.interest_priority DESC
    """).fetchall()
    db.close()
    def quadrant(inf, ints):
        if inf >= 4 and ints >= 4:
            return 'Ключевые игроки'
        if inf >= 4:
            return 'Удовлетворять'
        if ints >= 4:
            return 'Держать в курсе'
        return 'Наблюдать'
    key = sum(1 for t in types if quadrant(t['inf'], t['ints']) == 'Ключевые игроки')
    cards = [('Всего стейкхолдеров', st_total, '#2c3e50'),
             ('Типов', len(types), '#2c3e50'),
             ('Ключевые игроки', key, '#e74c3c')]
    rows = [[t['name'], t['inf'], t['ints'], t['cnt'], quadrant(t['inf'], t['ints'])] for t in types]
    return _report_page('Отчёт: Стейкхолдеры', cards, [
        {'title': 'Матрица власти и интереса (по типам)', 'headers': ['Тип', 'Влияние', 'Интерес', 'Кол-во', 'Квадрант'], 'rows': rows},
    ])

@app.route('/reports/employees')
def report_employees():
    db = get_db()
    emp_total = db.execute("SELECT COUNT(*) FROM employee WHERE is_deleted=0").fetchone()[0]
    emp_avail = db.execute("""
        SELECT COUNT(*) FROM employee e JOIN employee_status es ON e.status_id=es.id
        WHERE e.is_deleted=0 AND es.is_available=1
    """).fetchone()[0]
    emp_assigned = db.execute("SELECT COUNT(DISTINCT employee_id) FROM task_assignment WHERE is_deleted=0").fetchone()[0]
    load = db.execute("""
        SELECT e.id, e.last_name, e.first_name, pt.name pos, es.name st, es.is_available av,
               (SELECT COUNT(*) FROM task_assignment ta WHERE ta.employee_id=e.id AND ta.is_deleted=0) acnt,
               COALESCE((SELECT SUM(ta.share) FROM task_assignment ta WHERE ta.employee_id=e.id AND ta.is_deleted=0), 0) lshare
        FROM employee e
        JOIN position_type pt ON e.position_type_id=pt.id
        JOIN employee_status es ON e.status_id=es.id
        WHERE e.is_deleted=0
        ORDER BY lshare DESC
    """).fetchall()
    by_pos = db.execute("""
        SELECT pt.name, COUNT(e.id) cnt,
               COALESCE(SUM(CASE WHEN es.is_available=1 THEN 1 ELSE 0 END), 0) avail
        FROM position_type pt
        LEFT JOIN employee e ON e.position_type_id=pt.id AND e.is_deleted=0
        LEFT JOIN employee_status es ON e.status_id=es.id
        WHERE pt.is_deleted=0
        GROUP BY pt.id ORDER BY pt.name
    """).fetchall()
    eff = {l['id']: _employee_effective_load(db, l['id']) for l in load}
    db.close()
    overloaded = sum(1 for l in load if eff[l['id']] > 1.0)
    cards = [('Всего сотрудников', emp_total, '#2c3e50'),
             ('Доступно', emp_avail, '#27ae60'),
             ('Заняты в задачах', emp_assigned, '#2c3e50'),
             ('Перегружены (>100%)', overloaded, '#e74c3c')]
    rows = [[f'<a href="{url_for("employee_detail", id=l["id"])}">{l["last_name"]} {l["first_name"]}</a>', l['pos'], l['st'], l['acnt'], f"{round(eff[l['id']] * 100)}%"] for l in load]
    rows2 = [[p['name'], p['cnt'], p['avail']] for p in by_pos]
    return _report_page('Отчёт: Сотрудники', cards, [
        {'title': 'Загрузка сотрудников', 'headers': ['Фамилия', 'Имя', 'Должность', 'Статус', 'Назначений', 'Загрузка %'], 'rows': rows},
        {'title': 'Состав по должностям', 'headers': ['Должность', 'Сотрудников', 'Доступно'], 'rows': rows2},
    ])

@app.route('/reports/requirements')
def report_requirements():
    db = get_db()
    req_total = db.execute("SELECT COUNT(*) FROM requirement WHERE is_deleted=0").fetchone()[0]
    req_criteria = db.execute("""
        SELECT COUNT(*) FROM requirement
        WHERE is_deleted=0 AND acceptance_criteria IS NOT NULL AND acceptance_criteria <> ''
    """).fetchone()[0]
    req_impl = db.execute("""
        SELECT COUNT(DISTINCT r.id) FROM requirement r
        WHERE r.is_deleted=0 AND EXISTS (SELECT 1 FROM task t WHERE t.requirement_id=r.id AND t.is_deleted=0)
    """).fetchone()[0]
    by_proj = db.execute("""
        SELECT p.id, p.name, COUNT(r.id) total,
               COALESCE(SUM(CASE WHEN r.acceptance_criteria IS NOT NULL AND r.acceptance_criteria <> '' THEN 1 ELSE 0 END), 0) crit,
               COALESCE(SUM(CASE WHEN EXISTS (SELECT 1 FROM task t WHERE t.requirement_id=r.id AND t.is_deleted=0) THEN 1 ELSE 0 END), 0) impl
        FROM project p LEFT JOIN requirement r ON r.project_id=p.id AND r.is_deleted=0
        WHERE p.is_deleted=0 GROUP BY p.id ORDER BY p.name
    """).fetchall()
    by_type = db.execute("""
        SELECT rt.name, COUNT(r.id) cnt FROM requirement_type rt
        LEFT JOIN requirement r ON r.requirement_type_id=rt.id AND r.is_deleted=0
        WHERE rt.is_deleted=0 GROUP BY rt.id ORDER BY rt.name
    """).fetchall()
    by_prio = db.execute("""
        SELECT pr.name, COUNT(r.id) cnt FROM priority pr
        LEFT JOIN requirement r ON r.priority_id=pr.id AND r.is_deleted=0
        WHERE pr.is_deleted=0 GROUP BY pr.id ORDER BY pr.weight
    """).fetchall()
    db.close()
    cards = [('Всего требований', req_total, '#2c3e50'),
             ('С критерием проверки', req_criteria, '#2c3e50'),
             ('Реализовано (есть задачи)', req_impl, '#27ae60'),
             ('Без задач', req_total - req_impl, '#e74c3c')]
    rows = [[f'<a href="{url_for("project_detail", id=p["id"])}">{p["name"]}</a>', p['total'], p['crit'], p['impl'], p['total'] - p['impl']] for p in by_proj]
    rows2 = [[t['name'], t['cnt']] for t in by_type]
    rows3 = [[t['name'], t['cnt']] for t in by_prio]
    return _report_page('Отчёт: Требования', cards, [
        {'title': 'По проектам', 'headers': ['Проект', 'Требований', 'С критерием', 'Реализовано', 'Без задач'], 'rows': rows},
        {'title': 'По типам', 'headers': ['Тип требования', 'Кол-во'], 'rows': rows2},
        {'title': 'По приоритетам', 'headers': ['Приоритет', 'Кол-во'], 'rows': rows3},
    ])

@app.route('/reports/stages')
def report_stages():
    db = get_db()
    st_total = db.execute("SELECT COUNT(*) FROM project_stage WHERE is_deleted=0").fetchone()[0]
    st_done = db.execute("""
        SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE ps.is_deleted=0 AND pss.name='Завершён'
    """).fetchone()[0]
    st_work = db.execute("""
        SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE ps.is_deleted=0 AND pss.name='В работе'
    """).fetchone()[0]
    st_over = db.execute("""
        SELECT COUNT(*) FROM project_stage ps JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE ps.is_deleted=0 AND ps.planned_end < date('now') AND pss.name NOT IN ('Завершён', 'Отменён')
    """).fetchone()[0]
    by_proj = db.execute("""
        SELECT p.id, p.name, COUNT(ps.id) total,
               SUM(CASE WHEN pss.name='Завершён' THEN 1 ELSE 0 END) done,
               SUM(CASE WHEN pss.name='В работе' THEN 1 ELSE 0 END) work,
               SUM(CASE WHEN ps.planned_end < date('now') AND pss.name NOT IN ('Завершён', 'Отменён') THEN 1 ELSE 0 END) over
        FROM project p
        LEFT JOIN project_stage ps ON ps.project_id=p.id AND ps.is_deleted=0
        LEFT JOIN project_stage_status pss ON ps.status_id=pss.id
        WHERE p.is_deleted=0 GROUP BY p.id ORDER BY p.name
    """).fetchall()
    db.close()
    cards = [('Всего этапов', st_total, '#2c3e50'),
             ('В работе', st_work, '#3498db'),
             ('Завершено', st_done, '#27ae60'),
             ('Просрочено', st_over, '#e74c3c')]
    rows = [[f'<a href="{url_for("project_detail", id=p["id"])}">{p["name"]}</a>', p['total'], p['done'], p['work'], p['over']] for p in by_proj]
    return _report_page('Отчёт: Этапы', cards, [
        {'title': 'Этапы по проектам', 'headers': ['Проект', 'Всего', 'Завершено', 'В работе', 'Просрочено'], 'rows': rows},
    ])

@app.route('/reports/tasks')
def report_tasks():
    db = get_db()
    t_total = db.execute("SELECT COUNT(*) FROM task WHERE is_deleted=0").fetchone()[0]
    t_done = db.execute("""
        SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id=ts.id
        WHERE t.is_deleted=0 AND ts.name='Выполнена'
    """).fetchone()[0]
    t_work = db.execute("""
        SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id=ts.id
        WHERE t.is_deleted=0 AND ts.name IN ('Новая', 'В работе')
    """).fetchone()[0]
    t_over = db.execute("""
        SELECT COUNT(*) FROM task t JOIN task_status ts ON t.status_id=ts.id
        WHERE t.is_deleted=0 AND t.deadline < date('now') AND ts.name NOT IN ('Выполнена', 'Отменена')
    """).fetchone()[0]
    t_noexec = db.execute("""
        SELECT COUNT(*) FROM task t WHERE t.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta WHERE ta.task_id=t.id AND ta.task_kind='task' AND ta.is_deleted=0)
    """).fetchone()[0]
    by_status = db.execute("""
        SELECT ts.name, ts.color, COUNT(t.id) cnt FROM task_status ts
        LEFT JOIN task t ON t.status_id=ts.id AND t.is_deleted=0
        WHERE ts.is_deleted=0 GROUP BY ts.id ORDER BY ts.id
    """).fetchall()
    by_prio = db.execute("""
        SELECT pr.name, COUNT(t.id) cnt FROM priority pr
        LEFT JOIN task t ON t.priority_id=pr.id AND t.is_deleted=0
        WHERE pr.is_deleted=0 GROUP BY pr.id ORDER BY pr.weight
    """).fetchall()
    noexec_list = db.execute("""
        SELECT t.id, t.description, pr.name prio, ts.name st,
               p.id pid, p.name pname, ps.id stage_id, pst.name stype
        FROM task t
        JOIN priority pr ON t.priority_id=pr.id
        JOIN task_status ts ON t.status_id=ts.id
        LEFT JOIN project_stage ps ON t.stage_id=ps.id
        LEFT JOIN project_stage_type pst ON ps.stage_type_id=pst.id
        LEFT JOIN project p ON p.id = COALESCE(ps.project_id, (SELECT project_id FROM requirement WHERE id=t.requirement_id))
        WHERE t.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta WHERE ta.task_id=t.id AND ta.task_kind='task' AND ta.is_deleted=0)
    """).fetchall()
    db.close()
    cards = [('Всего задач', t_total, '#2c3e50'),
             ('В работе', t_work, '#3498db'),
             ('Выполнено', t_done, '#27ae60'),
             ('Просрочено', t_over, '#e74c3c'),
             ('Без исполнителя', t_noexec, '#f39c12')]
    rows = [[f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["name"]}</span>', s['cnt']] for s in by_status]
    rows2 = [[t['name'], t['cnt']] for t in by_prio]
    rows3 = [[f'<a href="{url_for("task_detail", id=t["id"])}">#{t["id"]}</a>',
              f'<a href="{url_for("project_detail", id=t["pid"])}">{t["pname"]}</a>' if t['pid'] else '-',
              f'<a href="{url_for("project_stage_detail", id=t["stage_id"])}">{t["stype"]}</a>' if t['stage_id'] else '-',
              t['description'][:60], t['prio'], t['st']] for t in noexec_list]
    return _report_page('Отчёт: Задачи', cards, [
        {'title': 'По статусам', 'headers': ['Статус', 'Кол-во'], 'rows': rows},
        {'title': 'По приоритетам', 'headers': ['Приоритет', 'Кол-во'], 'rows': rows2},
        {'title': 'Задачи без исполнителя', 'headers': ['ID', 'Проект', 'Этап', 'Описание', 'Приоритет', 'Статус'], 'rows': rows3},
    ])

@app.route('/reports/subtasks')
def report_subtasks():
    db = get_db()
    s_total = db.execute("SELECT COUNT(*) FROM subtask WHERE is_deleted=0").fetchone()[0]
    s_done = db.execute("""
        SELECT COUNT(*) FROM subtask s JOIN task_status ts ON s.status_id=ts.id
        WHERE s.is_deleted=0 AND ts.name='Выполнена'
    """).fetchone()[0]
    s_work = db.execute("""
        SELECT COUNT(*) FROM subtask s JOIN task_status ts ON s.status_id=ts.id
        WHERE s.is_deleted=0 AND ts.name IN ('Новая', 'В работе')
    """).fetchone()[0]
    s_over = db.execute("""
        SELECT COUNT(*) FROM subtask s JOIN task_status ts ON s.status_id=ts.id
        WHERE s.is_deleted=0 AND s.deadline < date('now') AND ts.name NOT IN ('Выполнена', 'Отменена')
    """).fetchone()[0]
    s_noexec = db.execute("""
        SELECT COUNT(*) FROM subtask s WHERE s.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta WHERE ta.task_id=s.id AND ta.task_kind='subtask' AND ta.is_deleted=0)
    """).fetchone()[0]
    by_status = db.execute("""
        SELECT ts.name, ts.color, COUNT(s.id) cnt FROM task_status ts
        LEFT JOIN subtask s ON s.status_id=ts.id AND s.is_deleted=0
        WHERE ts.is_deleted=0 GROUP BY ts.id ORDER BY ts.id
    """).fetchall()
    noexec_list = db.execute("""
        SELECT s.id, t.id parent_id, t.description parent, s.description, pr.name prio, ts.name st
        FROM subtask s
        JOIN task t ON s.parent_task_id=t.id
        JOIN priority pr ON s.priority_id=pr.id
        JOIN task_status ts ON s.status_id=ts.id
        WHERE s.is_deleted=0 AND NOT EXISTS (
            SELECT 1 FROM task_assignment ta WHERE ta.task_id=s.id AND ta.task_kind='subtask' AND ta.is_deleted=0)
    """).fetchall()
    db.close()
    cards = [('Всего подзадач', s_total, '#2c3e50'),
             ('В работе', s_work, '#3498db'),
             ('Выполнено', s_done, '#27ae60'),
             ('Просрочено', s_over, '#e74c3c'),
             ('Без исполнителя', s_noexec, '#f39c12')]
    rows = [[f'<span class="badge" style="background: {s["color"] or "#95a5a6"}">{s["name"]}</span>', s['cnt']] for s in by_status]
    rows2 = [[f'<a href="{url_for("subtask_detail", id=s["id"])}">#{s["id"]}</a>',
              f'<a href="{url_for("task_detail", id=s["parent_id"])}">{s["parent"][:50]}</a>',
              s['description'][:50], s['prio'], s['st']] for s in noexec_list]
    return _report_page('Отчёт: Подзадачи', cards, [
        {'title': 'По статусам', 'headers': ['Статус', 'Кол-во'], 'rows': rows},
        {'title': 'Подзадачи без исполнителя', 'headers': ['ID', 'Родительская задача', 'Описание', 'Приоритет', 'Статус'], 'rows': rows2},
    ])

@app.route('/reports/assignments')
def report_assignments():
    db = get_db()
    a_total = db.execute("SELECT COUNT(*) FROM task_assignment WHERE is_deleted=0").fetchone()[0]
    a_task = db.execute("SELECT COUNT(*) FROM task_assignment WHERE is_deleted=0 AND task_kind='task'").fetchone()[0]
    a_sub = db.execute("SELECT COUNT(*) FROM task_assignment WHERE is_deleted=0 AND task_kind='subtask'").fetchone()[0]
    by_emp = db.execute("""
        SELECT e.id, e.last_name, e.first_name, pt.name pos,
               COALESCE(SUM(CASE WHEN ta.task_kind='task' THEN ta.share ELSE 0 END), 0) task_share,
               COALESCE(SUM(CASE WHEN ta.task_kind='subtask' THEN ta.share ELSE 0 END), 0) sub_share,
               COUNT(ta.id) acnt
        FROM employee e
        LEFT JOIN task_assignment ta ON ta.employee_id=e.id AND ta.is_deleted=0
        JOIN position_type pt ON e.position_type_id=pt.id
        WHERE e.is_deleted=0
        GROUP BY e.id ORDER BY (task_share + sub_share) DESC
    """).fetchall()
    eff = {a['id']: _employee_effective_load(db, a['id']) for a in by_emp}
    db.close()
    max_load = max(eff.values(), default=0)
    cards = [('Назначений всего', a_total, '#2c3e50'),
             ('По задачам', a_task, '#3498db'),
             ('По подзадачам', a_sub, '#27ae60'),
             ('Максимальная загрузка', f'{round(max_load * 100)}%', '#e74c3c')]
    rows = [[f'<a href="{url_for("employee_detail", id=a["id"])}">{a["last_name"]} {a["first_name"]}</a>', a['pos'], f"{round((eff[a['id']]) * 100)}%",
             '—', f"{round(eff[a['id']] * 100)}%", a['acnt']] for a in by_emp]
    return _report_page('Отчёт: Назначения', cards, [
        {'title': 'Загрузка по сотрудникам', 'headers': ['Сотрудник', 'Должность', 'Задачи (доля)', 'Подзадачи (доля)', 'Итого %', 'Назначений'], 'rows': rows},
    ])

@app.route('/reports/events')
def report_events():
    db = get_db()
    e_total = db.execute("SELECT COUNT(*) FROM event WHERE is_deleted=0").fetchone()[0]
    e_last30 = db.execute("""
        SELECT COUNT(*) FROM event WHERE is_deleted=0 AND occurred_at >= date('now', '-30 days')
    """).fetchone()[0]
    months = db.execute("""
        SELECT strftime('%Y-%m', occurred_at) m, COUNT(*) cnt
        FROM event WHERE is_deleted=0 GROUP BY m ORDER BY m DESC
    """).fetchall()
    recent = db.execute("SELECT * FROM event WHERE is_deleted=0 ORDER BY occurred_at DESC LIMIT 10").fetchall()
    db.close()
    cards = [('Всего событий', e_total, '#2c3e50'),
             ('За 30 дней', e_last30, '#3498db'),
             ('Последнее событие', recent[0]['occurred_at'] if recent else '-', '#2c3e50')]
    rows = [[m['m'], m['cnt']] for m in months]
    rows2 = [[f'<a href="{url_for("event_detail", id=e["id"])}">{e["occurred_at"]}</a>', e['description'], e['decision'] or '-'] for e in recent]
    return _report_page('Отчёт: События', cards, [
        {'title': 'Динамика по месяцам', 'headers': ['Месяц', 'Кол-во'], 'rows': rows},
        {'title': 'Последние события', 'headers': ['Дата', 'Описание', 'Решение'], 'rows': rows2},
    ])


