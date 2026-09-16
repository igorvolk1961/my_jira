"""Главная страница."""

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
    current_project_row,
    project_selector_html,
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

# ==================== ГЛАВНАЯ СТРАНИЦА ====================

@app.route('/')
def index():
    db = get_db()
    
    stats = {
        'projects': db.execute("SELECT COUNT(*) FROM project WHERE is_deleted=0").fetchone()[0],
        'tasks': db.execute("SELECT COUNT(*) FROM task WHERE is_deleted=0").fetchone()[0],
        'employees': db.execute("SELECT COUNT(*) FROM employee WHERE is_deleted=0").fetchone()[0],
        'events': db.execute("SELECT COUNT(*) FROM event WHERE is_deleted=0").fetchone()[0],
        'active_tasks': db.execute("""
            SELECT COUNT(*) FROM task t
            JOIN task_status ts ON t.status_id = ts.id
            WHERE t.is_deleted=0 AND ts.name IN ('Новая', 'В работе')
        """).fetchone()[0],
        'overdue_tasks': db.execute("""
            SELECT COUNT(*) FROM task
            WHERE is_deleted=0 AND deadline < date('now') AND status_id NOT IN (
                SELECT id FROM task_status WHERE name IN ('Выполнена', 'Отменена')
            )
        """).fetchone()[0]
    }
    
    project = current_project_row(db)
    selector = project_selector_html(db, project['id'] if project else None, next_url=url_for('index'))

    content = f'''
    <div class="card" style="padding:14px 20px;">
        {selector}
    </div>
    <div class="stats">
        <div class="stat-card">
            <h3>Всего проектов</h3>
            <div class="value">{stats['projects']}</div>
        </div>
        <div class="stat-card">
            <h3>Активных задач</h3>
            <div class="value">{stats['active_tasks']}</div>
        </div>
        <div class="stat-card">
            <h3>Просроченных задач</h3>
            <div class="value" style="color: {'#e74c3c' if stats['overdue_tasks'] > 0 else '#27ae60'}">{stats['overdue_tasks']}</div>
        </div>
        <div class="stat-card">
            <h3>Сотрудников</h3>
            <div class="value">{stats['employees']}</div>
        </div>
        <div class="stat-card">
            <h3>Событий</h3>
            <div class="value">{stats['events']}</div>
        </div>
    </div>
    
    <div class="card">
        <h2>Добро пожаловать в Учебный проектный офис!</h2>
        <p style="margin-top: 10px;">Используйте меню выше для управления проектами, задачами и персоналом.</p>
    </div>
    '''
    
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Главная', content=content)


