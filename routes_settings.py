"""Настройки приложения (администратор)."""

from app_core import (  # noqa: F401
    BASE_TEMPLATE,
    app,
    flash,
    get_db,
    get_setting,
    redirect,
    render_template_string,
    request,
    set_setting,
    url_for,
)

SETTING_KEY = 'allow_users_assign_subtask_executors'


@app.route('/settings', methods=['GET', 'POST'])
def settings_index():
    db = get_db()
    if request.method == 'POST':
        value = '1' if request.form.get('allow_users_assign_subtask_executors') else '0'
        set_setting(db, SETTING_KEY, value)
        db.commit()
        db.close()
        flash('Настройки сохранены', 'success')
        return redirect(url_for('settings_index'))
    enabled = get_setting(db, SETTING_KEY, '1') == '1'
    db.close()
    checked = 'checked' if enabled else ''
    content = f'''
    <div class="card" style="max-width: 720px;">
        <h2>Настройки</h2>
        <form method="POST" style="margin-top:14px;">
            <div class="form-group">
                <label style="font-weight:normal;">
                    <input type="checkbox" name="{SETTING_KEY}" value="1" {checked} style="width:auto; display:inline; margin-right:6px;">
                    Разрешить пользователям назначать исполнителей на подзадачи
                </label>
                <div class="muted" style="margin-top:6px;">
                    Если включено — любой пользователь может назначить исполнителем подзадачи любого сотрудника команды проекта.
                    Если выключено — пользователь может назначить только себя либо оставить подзадачу без исполнителя.
                </div>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Настройки', content=content)
