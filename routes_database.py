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
    current_project_row,
    current_user,
    is_admin,
    is_analyst,
    date,
    datetime,
    db_path_for,
    flash,
    fmt_timecode,
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
    try:
        project = current_project_row()
    except sqlite3.Error:
        project = None
    return {
        'current_db': current_db_name(),
        'current_user': current_user(),
        'is_admin': is_admin(),
        'is_analyst': is_analyst(),
        'current_project': project,
    }

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
    admin = is_admin()
    preselect = request.args.get('copy') or current
    rows = ''.join([f'''
        <tr>
            <td>{f}
                {f'<span class="badge" style="background:#27ae60">активная</span>' if f == current else ''}
            </td>
            <td>{os.path.getsize(db_path_for(f)):,} байт</td>
            <td>
                {'' if f == current else f'<a href="{url_for("database_use", name=f)}" class="btn btn-primary">Использовать</a> '}
                {f'<a href="{url_for("database_index", copy=f)}" class="btn btn-warning">Копировать</a> ' if admin else ''}
                <a href="{url_for("database_delete", name=f)}" class="btn btn-danger" onclick="return confirm(\'Удалить БД?\')">Удалить</a>
            </td>
        </tr>''' for f in files])
    source_options = ''.join([
        f'<option value="{f}" {"selected" if f == preselect else ""}>{f}</option>' for f in files])
    copy_card = f'''
    <div class="card">
        <h2>Скопировать БД</h2>
        <p class="muted" style="margin-top:6px;">
            Копия файла базы данных — удобно для отдельной БД на урок (каждый урок или два).
            Копия создаётся без изменений; при необходимости данные удаляются вручную.
        </p>
        <form method="POST" action="{url_for('database_copy')}">
            <div class="form-group">
                <label>Исходная БД</label>
                <select name="source" required>{source_options}</select>
            </div>
            <div class="form-group">
                <label>Имя копии</label>
                <input type="text" name="name" placeholder="например, urok_2" required>
            </div>
            <div class="form-group">
                <label style="font-weight:normal;">
                    <input type="checkbox" name="switch" value="1" checked style="width:auto; display:inline; margin-right:6px;">
                    Переключиться на копию
                </label>
            </div>
            <button type="submit" class="btn btn-success">Создать копию</button>
        </form>
    </div>''' if admin else ''
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
    {copy_card}
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
        init_db(path)  # мигрируем существующую БД (идемпотентно)
        flash(f'БД «{name}» уже существует — переключились на неё', 'warning')
    else:
        init_db(path)
        flash(f'Создана БД «{name}»', 'success')
    session['db_name'] = name
    return redirect(url_for('database_index'))

@app.route('/database/copy', methods=['POST'])
def database_copy():
    source = _sanitize_db_name(request.form.get('source') or current_db_name())
    name = _sanitize_db_name(request.form.get('name'))
    if not source or not os.path.exists(db_path_for(source)):
        flash('Исходная БД не найдена', 'error')
        return redirect(url_for('database_index'))
    if not name:
        flash('Некорректное имя копии', 'error')
        return redirect(url_for('database_index'))
    if name == source:
        flash('Имя копии должно отличаться от исходной БД', 'error')
        return redirect(url_for('database_index'))
    dest = db_path_for(name)
    if os.path.exists(dest):
        flash(f'БД «{name}» уже существует', 'error')
        return redirect(url_for('database_index'))
    try:
        # Снимок файла: основной файл и WAL/SHM, если они есть.
        shutil.copy2(db_path_for(source), dest)
        for suffix in ('-wal', '-shm'):
            src_extra = db_path_for(source) + suffix
            if os.path.exists(src_extra):
                shutil.copy2(src_extra, dest + suffix)
        init_db(dest)
        flash(f'Создана копия «{name}» из «{source}»', 'success')
        if request.form.get('switch'):
            session['db_name'] = name
            flash(f'Активная БД: {name}', 'success')
    except (OSError, sqlite3.Error) as e:
        flash(f'Ошибка копирования: {e}', 'error')
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


