"""Журнал аудита (только чтение, для администратора)."""

from app_core import (  # noqa: F401
    BASE_TEMPLATE,
    app,
    assigner_sql,
    get_db,
    html,
    render_template_string,
    request,
    url_for,
)

_SORTS = {
    'created_at': 'a.created_at',
    'user': 'user_name',
    'action': 'a.action',
    'project': 'project_name',
}


@app.route('/audit')
def audit_index():
    db = get_db()
    project_id = request.args.get('project_id') or ''
    position_id = request.args.get('position_id') or ''
    user_id = request.args.get('user_id') or ''
    sort = request.args.get('sort') or 'created_at'
    direction = request.args.get('dir') or 'desc'
    order_col = _SORTS.get(sort, 'a.created_at')
    order_dir = 'ASC' if str(direction).lower() == 'asc' else 'DESC'

    where = []
    params = []
    if project_id.isdigit():
        where.append('a.project_id=?')
        params.append(int(project_id))
    if position_id.isdigit():
        where.append('a.position_id=?')
        params.append(int(position_id))
    if user_id.isdigit():
        where.append('a.user_id=?')
        params.append(int(user_id))
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    rows = db.execute(f"""
        SELECT a.*, u.login,
               {assigner_sql('ae', 'u', 'a.user_login')} AS user_name,
               p.name AS project_name,
               pt.name AS position_name
        FROM audit_log a
        LEFT JOIN app_user u ON a.user_id = u.id
        LEFT JOIN employee ae ON u.employee_id = ae.id
        LEFT JOIN project p ON a.project_id = p.id
        LEFT JOIN position_type pt ON a.position_id = pt.id
        {where_sql}
        ORDER BY {order_col} {order_dir}, a.id {order_dir}
        LIMIT 1000
    """, tuple(params)).fetchall()
    projects = db.execute("SELECT id, name FROM project WHERE is_deleted=0 ORDER BY name").fetchall()
    positions = db.execute("SELECT id, name FROM position_type WHERE is_deleted=0 ORDER BY name").fetchall()
    users = db.execute("""SELECT u.id, u.login,
                                 COALESCE(TRIM(e.last_name || ' ' || e.first_name), u.login) AS name
                          FROM app_user u LEFT JOIN employee e ON u.employee_id=e.id
                          WHERE u.is_deleted=0 ORDER BY name""").fetchall()
    db.close()

    def opts(items, selected):
        out = '<option value="">— все —</option>'
        for it in items:
            label = it['name']
            out += f'<option value="{it["id"]}" {"selected" if str(it["id"]) == str(selected) else ""}>{html.escape(label)}</option>'
        return out

    project_opts = opts(projects, project_id)
    position_opts = opts(positions, position_id)
    user_opts = opts(users, user_id)

    rows_html = ''.join([f'''
        <tr>
            <td>{html.escape(str(r['created_at']))}</td>
            <td>{html.escape(str(r['user_name']))}</td>
            <td>{html.escape(str(r['action']))}</td>
            <td>{html.escape(str(r['entity_type'] or ''))} {('#' + str(r['entity_id'])) if r['entity_id'] else ''}</td>
            <td>{html.escape(str(r['project_name'] or '—'))}</td>
            <td>{html.escape(str(r['position_name'] or '—'))}</td>
            <td>{html.escape(str(r['details'] or ''))}</td>
        </tr>''' for r in rows])
    if not rows_html:
        rows_html = '<tr><td colspan="7" class="muted">Записей нет</td></tr>'

    def sort_link(label, key):
        nd = 'asc' if (sort == key and order_dir == 'DESC') else 'desc'
        return f'<a href="{url_for("audit_index", project_id=project_id, position_id=position_id, user_id=user_id, sort=key, dir=nd)}">{label}</a>'

    content = f'''
    <div class="card">
        <h2>Аудит действий</h2>
        <form method="GET" style="margin-top:10px;">
            <div class="form-group">
                <label>Проект</label>
                <select name="project_id">{project_opts}</select>
            </div>
            <div class="form-group">
                <label>Должность</label>
                <select name="position_id">{position_opts}</select>
            </div>
            <div class="form-group">
                <label>Пользователь</label>
                <select name="user_id">{user_opts}</select>
            </div>
            <button type="submit" class="btn btn-primary">Применить</button>
            <a href="{url_for('audit_index')}" class="btn btn-warning">Сбросить</a>
        </form>
    </div>
    <div class="card">
        <table>
            <thead><tr>
                <th>{sort_link('Дата', 'created_at')}</th>
                <th>{sort_link('Пользователь', 'user')}</th>
                <th>{sort_link('Действие', 'action')}</th>
                <th>Объект</th>
                <th>{sort_link('Проект', 'project')}</th>
                <th>Должность</th>
                <th>Детали</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Аудит', content=content)
