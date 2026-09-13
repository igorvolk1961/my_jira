"""Справочники (CRUD)."""

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

# ==================== ПРИОРИТЕТЫ ====================

@app.route('/priorities')
def priorities_list():
    db = get_db()
    priorities = db.execute("SELECT * FROM priority WHERE is_deleted=0 ORDER BY weight").fetchall()
    
    rows = ''.join([f'''
        <tr>
            <td>{p['id']}</td>
            <td>{p['name']}</td>
            <td>{p['weight']}</td>
            <td>
                <a href="{url_for('priority_edit', id=p['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('priority_delete', id=p['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for p in priorities])
    
    content = f'''
    <div class="card">
        <h2>Приоритеты</h2>
        <a href="{url_for('priority_create')}" class="btn btn-success">+ Добавить приоритет</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Название</th><th>Вес</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Приоритеты', content=content)

@app.route('/priorities/create', methods=['GET', 'POST'])
def priority_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO priority (name, weight) VALUES (?, ?)",
                  (request.form['name'], int(request.form['weight'])))
        db.commit()
        db.close()
        flash('Приоритет создан', 'success')
        return redirect(url_for('priorities_list'))
    
    content = f'''
    <div class="card">
        <h2>Новый приоритет</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Вес (1-5)</label>
                <input type="number" name="weight" min="1" max="5" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('priorities_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый приоритет', content=content)

@app.route('/priorities/edit/<int:id>', methods=['GET', 'POST'])
def priority_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE priority SET name=?, weight=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], int(request.form['weight']), id))
        db.commit()
        db.close()
        flash('Приоритет обновлён', 'success')
        return redirect(url_for('priorities_list'))
    
    priority = db.execute("SELECT * FROM priority WHERE id=?", (id,)).fetchone()
    if not priority:
        db.close()
        flash('Приоритет не найден', 'error')
        return redirect(url_for('priorities_list'))
    db.close()
    
    content = f'''
    <div class="card">
        <h2>Редактировать приоритет</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{priority['name']}" required>
            </div>
            <div class="form-group">
                <label>Вес (1-5)</label>
                <input type="number" name="weight" value="{priority['weight']}" min="1" max="5" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('priorities_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать приоритет', content=content)

@app.route('/priorities/delete/<int:id>')
def priority_delete(id):
    db = get_db()
    db.execute("UPDATE priority SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Приоритет удалён', 'success')
    return redirect(url_for('priorities_list'))


# ==================== ТИПЫ СТЕЙКХОЛДЕРОВ ====================

@app.route('/stakeholder_types')
def stakeholder_types_list():
    db = get_db()
    types = db.execute("SELECT * FROM stakeholder_type WHERE is_deleted=0 ORDER BY id").fetchall()
    
    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>{t['influence_priority']}</td>
            <td>{t['interest_priority']}</td>
            <td>
                <a href="{url_for('stakeholder_type_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('stakeholder_type_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in types])
    
    content = f'''
    <div class="card">
        <h2>Типы стейкхолдеров</h2>
        <a href="{url_for('stakeholder_type_create')}" class="btn btn-success">+ Добавить тип</a>
        <table>
            <thead>
                <tr><th>ID</th><th>Название</th><th>Влияние</th><th>Заинтересованность</th><th>Действия</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Типы стейкхолдеров', content=content)

@app.route('/stakeholder_types/create', methods=['GET', 'POST'])
def stakeholder_type_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO stakeholder_type (name, influence_priority, interest_priority) VALUES (?, ?, ?)",
                  (request.form['name'], int(request.form['influence_priority']), int(request.form['interest_priority'])))
        db.commit()
        db.close()
        flash('Тип стейкхолдера создан', 'success')
        return redirect(url_for('stakeholder_types_list'))
    
    content = f'''
    <div class="card">
        <h2>Новый тип стейкхолдера</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Приоритет влияния (1-5)</label>
                <input type="number" name="influence_priority" min="1" max="5" required>
            </div>
            <div class="form-group">
                <label>Приоритет заинтересованности (1-5)</label>
                <input type="number" name="interest_priority" min="1" max="5" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('stakeholder_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый тип стейкхолдера', content=content)

@app.route('/stakeholder_types/edit/<int:id>', methods=['GET', 'POST'])
def stakeholder_type_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("""UPDATE stakeholder_type SET name=?, influence_priority=?, interest_priority=?, 
                     updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                  (request.form['name'], int(request.form['influence_priority']),
                   int(request.form['interest_priority']), id))
        db.commit()
        db.close()
        flash('Тип стейкхолдера обновлён', 'success')
        return redirect(url_for('stakeholder_types_list'))
    
    stype = db.execute("SELECT * FROM stakeholder_type WHERE id=?", (id,)).fetchone()
    if not stype:
        db.close()
        flash('Тип стейкхолдера не найден', 'error')
        return redirect(url_for('stakeholder_types_list'))
    db.close()
    
    content = f'''
    <div class="card">
        <h2>Редактировать тип стейкхолдера</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{stype['name']}" required>
            </div>
            <div class="form-group">
                <label>Приоритет влияния (1-5)</label>
                <input type="number" name="influence_priority" value="{stype['influence_priority']}" min="1" max="5" required>
            </div>
            <div class="form-group">
                <label>Приоритет заинтересованности (1-5)</label>
                <input type="number" name="interest_priority" value="{stype['interest_priority']}" min="1" max="5" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('stakeholder_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать тип стейкхолдера', content=content)

@app.route('/stakeholder_types/delete/<int:id>')
def stakeholder_type_delete(id):
    db = get_db()
    db.execute("UPDATE stakeholder_type SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Тип стейкхолдера удалён', 'success')
    return redirect(url_for('stakeholder_types_list'))


#==================== ТИПЫ ТРЕБОВАНИЙ ====================

@app.route('/requirement_types')
def requirement_types_list():
    db = get_db()
    types = db.execute("SELECT * FROM requirement_type WHERE is_deleted=0 ORDER BY id").fetchall()
    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>
                <a href="{url_for('requirement_type_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('requirement_type_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in types])

    content = f'''
    <div class="card">
        <h2>Типы требований</h2>
        <a href="{url_for('requirement_type_create')}" class="btn btn-success">+ Добавить тип</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Типы требований', content=content)

@app.route('/requirement_types/create', methods=['GET', 'POST'])
def requirement_type_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO requirement_type (name) VALUES (?)", (request.form['name'],))
        db.commit()
        db.close()
        flash('Тип требования создан', 'success')
        return redirect(url_for('requirement_types_list'))

    content = f'''
    <div class="card">
        <h2>Новый тип требования</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('requirement_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый тип требования', content=content)

@app.route('/requirement_types/edit/<int:id>', methods=['GET', 'POST'])
def requirement_type_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE requirement_type SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], id))
        db.commit()
        db.close()
        flash('Тип требования обновлён', 'success')
        return redirect(url_for('requirement_types_list'))

    rtype = db.execute("SELECT * FROM requirement_type WHERE id=?", (id,)).fetchone()
    if not rtype:
        db.close()
        flash('Тип требования не найден', 'error')
        return redirect(url_for('requirement_types_list'))
    db.close()
    content = f'''
    <div class="card">
        <h2>Редактировать тип требования</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{rtype['name']}" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('requirement_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать тип требования', content=content)

@app.route('/requirement_types/delete/<int:id>')
def requirement_type_delete(id):
    db = get_db()
    db.execute("UPDATE requirement_type SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Тип требования удалён', 'success')
    return redirect(url_for('requirement_types_list'))

#==================== ТИПЫ ДОЛЖНОСТЕЙ ====================
@app.route('/position_types')
def position_types_list():
    db = get_db()
    types = db.execute("SELECT * FROM position_type WHERE is_deleted=0 ORDER BY id").fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>
                <a href="{url_for('position_type_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('position_type_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in types])

    content = f'''
    <div class="card">
        <h2>Типы должностей</h2>
        <a href="{url_for('position_type_create')}" class="btn btn-success">+ Добавить тип</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Типы должностей', content=content)

@app.route('/position_types/create', methods=['GET', 'POST'])
def position_type_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO position_type (name) VALUES (?)", (request.form['name'],))
        db.commit()
        db.close()
        flash('Тип должности создан', 'success')
        return redirect(url_for('position_types_list'))
    content = f'''
    <div class="card">
        <h2>Новый тип должности</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('position_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый тип должности', content=content)

@app.route('/position_types/edit/<int:id>', methods=['GET', 'POST'])
def position_type_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE position_type SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], id))
        db.commit()
        db.close()
        flash('Тип должности обновлён', 'success')
        return redirect(url_for('position_types_list'))

    ptype = db.execute("SELECT * FROM position_type WHERE id=?", (id,)).fetchone()
    if not ptype:
        db.close()
        flash('Тип должности не найден', 'error')
        return redirect(url_for('position_types_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать тип должности</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{ptype['name']}" required>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('position_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать тип должности', content=content)

@app.route('/position_types/delete/<int:id>')
def position_type_delete(id):
    db = get_db()
    db.execute("UPDATE position_type SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Тип должности удалён', 'success')
    return redirect(url_for('position_types_list'))


#==================== СТАТУСЫ СОТРУДНИКОВ ====================
@app.route('/employee_statuses')
def employee_statuses_list():
    db = get_db()
    statuses = db.execute("SELECT * FROM employee_status WHERE is_deleted=0 ORDER BY id").fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td>{s['name']}</td>
            <td>{'Да' if s['is_available'] else 'Нет'}</td>
            <td>
                <a href="{url_for('employee_status_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('employee_status_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in statuses])

    content = f'''
    <div class="card">
        <h2>Статусы сотрудников</h2>
        <a href="{url_for('employee_status_create')}" class="btn btn-success">+ Добавить статус</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Доступен</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Статусы сотрудников', content=content)

@app.route('/employee_statuses/create', methods=['GET', 'POST'])
def employee_status_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO employee_status (name, is_available) VALUES (?, ?)",
                  (request.form['name'], int(request.form.get('is_available', 0))))
        db.commit()
        db.close()
        flash('Статус сотрудника создан', 'success')
        return redirect(url_for('employee_statuses_list'))

    content = f'''
    <div class="card">
        <h2>Новый статус сотрудника</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Доступен для работы</label>
                <select name="is_available">
                    <option value="1">Да</option>
                    <option value="0">Нет</option>
                </select>
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('employee_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый статус сотрудника', content=content)

@app.route('/employee_statuses/edit/<int:id>', methods=['GET', 'POST'])
def employee_status_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE employee_status SET name=?, is_available=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], int(request.form.get('is_available', 0)), id))
        db.commit()
        db.close()
        flash('Статус сотрудника обновлён', 'success')
        return redirect(url_for('employee_statuses_list'))

    status = db.execute("SELECT * FROM employee_status WHERE id=?", (id,)).fetchone()
    if not status:
        db.close()
        flash('Статус сотрудника не найден', 'error')
        return redirect(url_for('employee_statuses_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать статус сотрудника</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{status['name']}" required>
            </div>
            <div class="form-group">
                <label>Доступен для работы</label>
                <select name="is_available">
                    <option value="1" {"selected" if status['is_available'] else ""}>Да</option>
                    <option value="0" {"selected" if not status['is_available'] else ""}>Нет</option>
                </select>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('employee_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать статус сотрудника', content=content)

@app.route('/employee_statuses/delete/<int:id>')
def employee_status_delete(id):
    db = get_db()
    db.execute("UPDATE employee_status SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Статус сотрудника удалён', 'success')
    return redirect(url_for('employee_statuses_list'))

#==================== ТИПЫ ЭТАПОВ ПРОЕКТА ====================
@app.route('/stage_types')
def stage_types_list():
    db = get_db()
    types = db.execute("SELECT * FROM project_stage_type WHERE is_deleted=0 ORDER BY sort_order").fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>{t['sort_order']}</td>
            <td>
                <a href="{url_for('stage_type_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('stage_type_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in types])

    content = f'''
    <div class="card">
        <h2>Типы этапов проекта</h2>
        <a href="{url_for('stage_type_create')}" class="btn btn-success">+ Добавить тип</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Порядок</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Типы этапов', content=content)

@app.route('/stage_types/create', methods=['GET', 'POST'])
def stage_type_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO project_stage_type (name, sort_order) VALUES (?, ?)",
                  (request.form['name'], int(request.form.get('sort_order', 0))))
        db.commit()
        db.close()
        flash('Тип этапа создан', 'success')
        return redirect(url_for('stage_types_list'))

    content = f'''
    <div class="card">
        <h2>Новый тип этапа</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Порядок</label>
                <input type="number" name="sort_order" value="0">
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('stage_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый тип этапа', content=content)

@app.route('/stage_types/edit/<int:id>', methods=['GET', 'POST'])
def stage_type_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE project_stage_type SET name=?, sort_order=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], int(request.form.get('sort_order', 0)), id))
        db.commit()
        db.close()
        flash('Тип этапа обновлён', 'success')
        return redirect(url_for('stage_types_list'))
    stype = db.execute("SELECT * FROM project_stage_type WHERE id=?", (id,)).fetchone()
    if not stype:
        db.close()
        flash('Тип этапа не найден', 'error')
        return redirect(url_for('stage_types_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать тип этапа</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{stype['name']}" required>
            </div>
            <div class="form-group">
                <label>Порядок</label>
                <input type="number" name="sort_order" value="{stype['sort_order']}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('stage_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать тип этапа', content=content)

@app.route('/stage_types/delete/<int:id>')
def stage_type_delete(id):
    db = get_db()
    db.execute("UPDATE project_stage_type SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Тип этапа удалён', 'success')
    return redirect(url_for('stage_types_list'))

#==================== СТАТУСЫ ЭТАПОВ ПРОЕКТА ====================
@app.route('/stage_statuses')
def stage_statuses_list():
    db = get_db()
    statuses = db.execute("SELECT * FROM project_stage_status WHERE is_deleted=0 ORDER BY id").fetchall()

    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td>{s['name']}</td>
            <td><span class="badge" style="background: {s['color'] or '#95a5a6'}">{s['color'] or '-'}</span></td>
            <td>
                <a href="{url_for('stage_status_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('stage_status_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in statuses])

    content = f'''
    <div class="card">
        <h2>Статусы этапов проекта</h2>
        <a href="{url_for('stage_status_create')}" class="btn btn-success">+ Добавить статус</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Цвет</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Статусы этапов', content=content)

@app.route('/stage_statuses/create', methods=['GET', 'POST'])
def stage_status_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO project_stage_status (name, color) VALUES (?, ?)",
                  (request.form['name'], request.form.get('color')))
        db.commit()
        db.close()
        flash('Статус этапа создан', 'success')
        return redirect(url_for('stage_statuses_list'))

    content = f'''
    <div class="card">
        <h2>Новый статус этапа</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Цвет (например: blue, green, red)</label>
                <input type="text" name="color">
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('stage_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый статус этапа', content=content)

@app.route('/stage_statuses/edit/<int:id>', methods=['GET', 'POST'])
def stage_status_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE project_stage_status SET name=?, color=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], request.form.get('color'), id))
        db.commit()
        db.close()
        flash('Статус этапа обновлён', 'success')
        return redirect(url_for('stage_statuses_list'))

    status = db.execute("SELECT * FROM project_stage_status WHERE id=?", (id,)).fetchone()
    if not status:
        db.close()
        flash('Статус этапа не найден', 'error')
        return redirect(url_for('stage_statuses_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать статус этапа</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{status['name']}" required>
            </div>
            <div class="form-group">
                <label>Цвет</label>
                <input type="text" name="color" value="{status['color'] or ''}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('stage_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать статус этапа', content=content)

@app.route('/stage_statuses/delete/<int:id>')
def stage_status_delete(id):
    db = get_db()
    db.execute("UPDATE project_stage_status SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Статус этапа удалён', 'success')
    return redirect(url_for('stage_statuses_list'))

#==================== СТАТУСЫ ЗАДАЧ ====================
@app.route('/task_statuses')
def task_statuses_list():
    db = get_db()
    statuses = db.execute("SELECT * FROM task_status WHERE is_deleted=0 ORDER BY id").fetchall()
    rows = ''.join([f'''
        <tr>
            <td>{s['id']}</td>
            <td>{s['name']}</td>
            <td><span class="badge" style="background: {s['color'] or '#95a5a6'}">{s['color'] or '-'}</span></td>
            <td>
                <a href="{url_for('task_status_edit', id=s['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('task_status_delete', id=s['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for s in statuses])

    content = f'''
    <div class="card">
        <h2>Статусы задач</h2>
        <a href="{url_for('task_status_create')}" class="btn btn-success">+ Добавить статус</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Цвет</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Статусы задач', content=content)

@app.route('/task_statuses/create', methods=['GET', 'POST'])
def task_status_create():
    if request.method == 'POST':
        db = get_db()
        db.execute("INSERT INTO task_status (name, color) VALUES (?, ?)",
                  (request.form['name'], request.form.get('color')))
        db.commit()
        db.close()
        flash('Статус задачи создан', 'success')
        return redirect(url_for('task_statuses_list'))

    content = f'''
    <div class="card">
        <h2>Новый статус задачи</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" required>
            </div>
            <div class="form-group">
                <label>Цвет</label>
                <input type="text" name="color">
            </div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('task_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый статус задачи', content=content)


@app.route('/task_statuses/edit/<int:id>', methods=['GET', 'POST'])
def task_status_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE task_status SET name=?, color=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (request.form['name'], request.form.get('color'), id))
        db.commit()
        db.close()
        flash('Статус задачи обновлён', 'success')
        return redirect(url_for('task_statuses_list'))
    status = db.execute("SELECT * FROM task_status WHERE id=?", (id,)).fetchone()
    if not status:
        db.close()
        flash('Статус задачи не найден', 'error')
        return redirect(url_for('task_statuses_list'))
    db.close()

    content = f'''
    <div class="card">
        <h2>Редактировать статус задачи</h2>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{status['name']}" required>
            </div>
            <div class="form-group">
                <label>Цвет</label>
                <input type="text" name="color" value="{status['color'] or ''}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('task_statuses_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать статус задачи', content=content)

@app.route('/task_statuses/delete/<int:id>')
def task_status_delete(id):
    db = get_db()
    db.execute("UPDATE task_status SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Статус задачи удалён', 'success')
    return redirect(url_for('task_statuses_list'))


#==================== ТИПЫ ЗАДАЧ ====================
@app.route('/task_types')
def task_types_list():
    db = get_db()
    types = db.execute("SELECT * FROM task_type WHERE is_deleted=0 ORDER BY id").fetchall()
    rows = ''.join([f'''
        <tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>
                <a href="{url_for('task_type_edit', id=t['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('task_type_delete', id=t['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for t in types])
    content = f'''
    <div class="card">
        <h2>Типы задач</h2>
        <a href="{url_for('task_type_create')}" class="btn btn-success">+ Добавить тип</a>
        <table>
            <thead><tr><th>ID</th><th>Название</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Типы задач', content=content)

@app.route('/task_types/create', methods=['GET', 'POST'])
def task_type_create():
    db = get_db()
    if request.method == 'POST':
        cur = db.execute("INSERT INTO task_type (name) VALUES (?)", (request.form['name'],))
        db.commit()
        db.close()
        flash('Тип задачи создан', 'success')
        return redirect(url_for('task_types_list'))
    content = f'''
    <div class="card">
        <h2>Новый тип задачи</h2>
        <form method="POST">
            <div class="form-group"><label>Название</label><input type="text" name="name" required></div>
            <button type="submit" class="btn btn-success">Создать</button>
            <a href="{url_for('task_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Новый тип задачи', content=content)

@app.route('/task_types/edit/<int:id>', methods=['GET', 'POST'])
def task_type_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE task_type SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (request.form['name'], id))
        db.commit()
        db.close()
        flash('Тип задачи обновлён', 'success')
        return redirect(url_for('task_types_list'))
    t = db.execute("SELECT * FROM task_type WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not t:
        db.close()
        flash('Тип задачи не найден', 'error')
        return redirect(url_for('task_types_list'))
    db.close()
    content = f'''
    <div class="card">
        <h2>Редактировать тип задачи</h2>
        <form method="POST">
            <div class="form-group"><label>Название</label><input type="text" name="name" value="{t['name']}" required></div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('task_types_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать тип задачи', content=content)

@app.route('/task_types/delete/<int:id>')
def task_type_delete(id):
    db = get_db()
    db.execute("UPDATE task_type SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Тип задачи удалён', 'success')
    return redirect(url_for('task_types_list'))


