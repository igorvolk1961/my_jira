"""Пользовательский чат (общая лента)."""

from app_core import (  # noqa: F401
    BASE_TEMPLATE,
    app,
    current_user,
    flash,
    get_db,
    html,
    redirect,
    render_template_string,
    request,
    url_for,
)


@app.route('/chat')
def chat_index():
    db = get_db()
    rows = db.execute("""
        SELECT c.*, u.login
        FROM chat_message c LEFT JOIN app_user u ON c.user_id = u.id
        ORDER BY c.id DESC LIMIT 200
    """).fetchall()
    db.close()
    messages = list(reversed(rows))
    items = ''.join([f'''
        <div class="comment" style="margin-bottom:10px;">
            <strong>{html.escape(m['author'])}</strong>
            <span class="muted">· {html.escape(str(m['created_at']))}</span><br>
            {html.escape(m['text'])}
        </div>''' for m in messages])
    if not items:
        items = '<div class="muted">Сообщений пока нет</div>'
    user = current_user()
    if user:
        form = f'''
        <form method="POST" action="{url_for('chat_post')}" style="margin-top:14px;">
            <div class="form-group">
                <textarea name="text" required placeholder="Ваше сообщение"></textarea>
            </div>
            <button type="submit" class="btn btn-success">Отправить</button>
        </form>'''
    else:
        form = f'<div class="muted" style="margin-top:14px;">Чтобы писать в чат, <a href="{url_for("login")}">войдите</a>.</div>'
    content = f'''
    <div class="card">
        <h2>Чат</h2>
        {items}
        {form}
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Чат', content=content)


@app.route('/chat/post', methods=['POST'])
def chat_post():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    text = (request.form.get('text') or '').strip()
    if not text:
        flash('Сообщение не может быть пустым', 'error')
        return redirect(url_for('chat_index'))
    db = get_db()
    db.execute("INSERT INTO chat_message (user_id, author, text) VALUES (?, ?, ?)",
               (user['id'], user['full_name'], text))
    db.commit()
    db.close()
    return redirect(url_for('chat_index'))
