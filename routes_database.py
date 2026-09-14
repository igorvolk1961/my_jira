"""Управление базой данных."""

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
    current_user,
    is_admin,
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

#==================== УПРАВЛЕНИЕ БАЗОЙ ДАННЫХ ====================

@app.context_processor
def _inject_current_db():
    return {'current_db': current_db_name(), 'current_user': current_user(), 'is_admin': is_admin()}

def _sanitize_db_name(name):
    name = (name or '').strip()
    if not name or '/' in name or '\\' in name:
        return None
    if not name.endswith('.db'):
        name += '.db'
    if name.startswith('.') or '..' in name:
        return None
    if not all(ch.isalnum() or ch in '_.-' for ch in name):
        return None
    return name

def _list_databases():
    return sorted(f for f in os.listdir(DATABASE_DIR) if f.endswith('.db'))

@app.route('/database')
def database_index():
    current = current_db_name()
    files = _list_databases()
    rows = ''.join([f'''
        <tr>
            <td>{f}
                {f'<span class="badge" style="background:#27ae60">активная</span>' if f == current else ''}
            </td>
            <td>{os.path.getsize(db_path_for(f)):,} байт</td>
            <td>
                {'' if f == current else f'<a href="{url_for("database_use", name=f)}" class="btn btn-primary">Использовать</a> '}
                <a href="{url_for("database_delete", name=f)}" class="btn btn-danger" onclick="return confirm(\'Удалить БД?\')">Удалить</a>
            </td>
        </tr>''' for f in files])
    content = f'''
    <div class="card">
        <h2>Управление базой данных</h2>
        <p style="margin-top:10px;">Текущая активная БД: <strong>{current}</strong></p>
    </div>
    <div class="card">
        <h2>Создать новую БД</h2>
        <form method="POST" action="{url_for('database_create')}">
            <div class="form-group">
                <label>Имя новой БД</label>
                <input type="text" name="name" placeholder="например, projekt_alpha" required>
            </div>
            <button type="submit" class="btn btn-success">Создать и переключиться</button>
        </form>
    </div>
    <div class="card">
        <h2>Имеющиеся БД</h2>
        <table>
            <thead><tr><th>Имя</th><th>Размер</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='База данных', content=content)

@app.route('/database/create', methods=['POST'])
def database_create():
    name = _sanitize_db_name(request.form.get('name'))
    if not name:
        flash('Некорректное имя БД', 'error')
        return redirect(url_for('database_index'))
    path = db_path_for(name)
    if os.path.exists(path):
        flash(f'БД «{name}» уже существует — переключились на неё', 'warning')
    else:
        init_db(path)
        flash(f'Создана БД «{name}»', 'success')
    session['db_name'] = name
    return redirect(url_for('database_index'))

@app.route('/database/use/<name>')
def database_use(name):
    name = _sanitize_db_name(name)
    if not name or not os.path.exists(db_path_for(name)):
        flash('БД не найдена', 'error')
        return redirect(url_for('database_index'))
    # Мигрируем/дополняем выбранную БД (идемпотентно), иначе старые БД без новых таблиц дадут 500.
    init_db(db_path_for(name))
    session['db_name'] = name
    flash(f'Активная БД: {name}', 'success')
    return redirect(url_for('database_index'))

@app.route('/database/delete/<name>')
def database_delete(name):
    name = _sanitize_db_name(name)
    if not name or not os.path.exists(db_path_for(name)):
        flash('БД не найдена', 'error')
        return redirect(url_for('database_index'))
    if name == DEFAULT_DB_NAME:
        flash('Нельзя удалить основную БД', 'error')
        return redirect(url_for('database_index'))
    try:
        for suffix in ('', '-wal', '-shm'):
            p = db_path_for(name) + suffix
            if os.path.exists(p):
                os.remove(p)
        if session.get('db_name') == name:
            session['db_name'] = DEFAULT_DB_NAME
        flash(f'БД «{name}» удалена', 'success')
    except OSError as e:
        flash(f'Ошибка удаления: {e}', 'error')
    return redirect(url_for('database_index'))


