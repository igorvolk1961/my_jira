"""Аутентификация: вход, выход, регистрация."""

from app_core import (  # noqa: F401
    BASE_TEMPLATE,
    app,
    flash,
    get_db,
    redirect,
    render_template_string,
    request,
    safe_next,
    session,
    url_for,
)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_name = (request.form.get('login') or '').strip()
        password = request.form.get('password') or ''
        db = get_db()
        row = db.execute("SELECT * FROM app_user WHERE lower(login)=lower(?) AND is_deleted=0",
                         (login_name,)).fetchone()
        db.close()
        if row and row['password'] == password:
            session['user_id'] = row['id']
            flash('Вы вошли в систему', 'success')
            return redirect(safe_next(session.pop('next', None), url_for('index')))
        flash('Неверный логин или пароль', 'error')

    content = '''
    <div class="card" style="max-width: 480px; margin: 0 auto;">
        <h2>Вход</h2>
        <form method="POST">
            <div class="form-group">
                <label>Логин</label>
                <input type="text" name="login" required autofocus>
            </div>
            <div class="form-group">
                <label>Пароль</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="btn btn-success">Войти</button>
            <a href="''' + url_for('register') + '''" class="btn btn-primary">Регистрация</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Вход', content=content)


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        login_name = (request.form.get('login') or '').strip()
        password = request.form.get('password') or ''
        last_name = (request.form.get('last_name') or '').strip()
        first_name = (request.form.get('first_name') or '').strip()
        middle_name = (request.form.get('middle_name') or '').strip()
        if not (login_name and password and last_name and first_name and middle_name):
            flash('Все поля обязательны, пароль не может быть пустым', 'error')
            return redirect(url_for('register'))
        db = get_db()
        exists = db.execute("SELECT 1 FROM app_user WHERE lower(login)=lower(?)", (login_name,)).fetchone()
        if exists:
            db.close()
            flash('Пользователь с таким логином уже существует', 'error')
            return redirect(url_for('register'))
        pos = db.execute("SELECT id FROM position_type WHERE lower(name)=lower('Пользователь') AND is_deleted=0").fetchone()
        if not pos:
            pos_id = db.execute("INSERT INTO position_type (name) VALUES ('Пользователь')").lastrowid
        else:
            pos_id = pos[0]
        st = db.execute("SELECT id FROM employee_status WHERE lower(name)=lower('Работает') AND is_deleted=0").fetchone()
        if not st:
            status_id = db.execute("INSERT INTO employee_status (name, is_available) VALUES ('Работает', 1)").lastrowid
        else:
            status_id = st[0]
        cur = db.execute("""INSERT INTO employee (last_name, first_name, middle_name, position_type_id, status_id,
                            subordinates_total, subordinates_available, is_stackholder)
                            VALUES (?, ?, ?, ?, ?, 0, 0, 0)""",
                         (last_name, first_name, middle_name, pos_id, status_id))
        emp_id = cur.lastrowid
        db.execute("INSERT INTO app_user (login, password, role, employee_id) VALUES (?, ?, 'user', ?)",
                   (login_name, password, emp_id))
        db.commit()
        db.close()
        flash('Регистрация завершена — войдите с новыми учётными данными', 'success')
        return redirect(url_for('login'))

    content = '''
    <div class="card" style="max-width: 480px; margin: 0 auto;">
        <h2>Регистрация</h2>
        <form method="POST">
            <div class="form-group">
                <label>Логин</label>
                <input type="text" name="login" required autofocus>
            </div>
            <div class="form-group">
                <label>Пароль</label>
                <input type="password" name="password" required>
            </div>
            <div class="form-group">
                <label>Фамилия</label>
                <input type="text" name="last_name" required>
            </div>
            <div class="form-group">
                <label>Имя</label>
                <input type="text" name="first_name" required>
            </div>
            <div class="form-group">
                <label>Отчество</label>
                <input type="text" name="middle_name" required>
            </div>
            <button type="submit" class="btn btn-success">Зарегистрироваться</button>
            <a href="''' + url_for('login') + '''" class="btn btn-primary">Назад ко входу</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Регистрация', content=content)
