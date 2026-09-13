"""Интервью, аудио и транскрипт."""

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

#==================== ИНТЕРВЬЮ СТЕЙКХОЛДЕРОВ ====================

@app.route('/interviews')
def interviews_list():
    db = get_db()
    items = db.execute("""
        SELECT i.*, s.last_name, s.first_name
        FROM interview i JOIN stakeholder s ON i.stakeholder_id=s.id
        WHERE i.is_deleted=0 ORDER BY i.scheduled_at DESC
    """).fetchall()
    rows = ''.join([f'''
        <tr>
            <td>{i['id']}</td>
            <td><a href="{url_for('stakeholder_detail', id=i['stakeholder_id'])}">{i['last_name']} {i['first_name']}</a></td>
            <td>{i['scheduled_at'] or '-'}</td>
            <td>
                <a href="{url_for('interview_detail', id=i['id'])}" class="btn btn-success">Открыть</a>
                <a href="{url_for('interview_edit', id=i['id'])}" class="btn btn-primary">Изменить</a>
                <a href="{url_for('interview_delete', id=i['id'])}" class="btn btn-danger" onclick="return confirm('Удалить?')">Удалить</a>
            </td>
        </tr>
    ''' for i in items])
    content = f'''
    <div class="card">
        <h2>Интервью стейкхолдеров</h2>
        <a href="{url_for('interview_create')}" class="btn btn-success">+ Назначить интервью</a>
        <table>
            <thead><tr><th>ID</th><th>Стейкхолдер</th><th>Дата-время</th><th>Действия</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    db.close()
    return render_template_string(BASE_TEMPLATE, title='Интервью', content=content)

@app.route('/interviews/create', methods=['GET', 'POST'])
def interview_create():
    db = get_db()
    if request.method == 'POST':
        cur = db.execute("INSERT INTO interview (stakeholder_id, scheduled_at) VALUES (?, ?)",
                         (int(request.form['stakeholder_id']), request.form.get('scheduled_at') or None))
        db.commit()
        new_id = cur.lastrowid
        db.close()
        flash('Интервью назначено', 'success')
        return redirect(url_for('interview_detail', id=new_id))
    pre_sh = request.args.get('stakeholder_id')
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    db.close()
    options = ''.join([f'<option value="{s["id"]}" {"selected" if str(s["id"]) == pre_sh else ""}>{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    content = f'''
    <div class="card">
        <h2>Новое интервью</h2>
        <form method="POST">
            <div class="form-group">
                <label>Стейкхолдер</label>
                <select name="stakeholder_id" required>{options}</select>
            </div>
            <div class="form-group">
                <label>Дата-время</label>
                <input type="datetime-local" name="scheduled_at">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('interviews_list')}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новое интервью', content=content)

@app.route('/interviews/edit/<int:id>', methods=['GET', 'POST'])
def interview_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE interview SET stakeholder_id=?, scheduled_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (int(request.form['stakeholder_id']), request.form.get('scheduled_at') or None, id))
        db.commit()
        db.close()
        flash('Интервью обновлено', 'success')
        return redirect(url_for('interview_detail', id=id))
    iv = db.execute("SELECT * FROM interview WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not iv:
        db.close()
        flash('Интервью не найдено', 'error')
        return redirect(url_for('interviews_list'))
    stakeholders = db.execute("SELECT * FROM stakeholder WHERE is_deleted=0").fetchall()
    db.close()
    options = ''.join([f'<option value="{s["id"]}" {"selected" if s["id"] == iv["stakeholder_id"] else ""}>{s["last_name"]} {s["first_name"]}</option>' for s in stakeholders])
    content = f'''
    <div class="card">
        <h2>Редактировать интервью</h2>
        <form method="POST">
            <div class="form-group">
                <label>Стейкхолдер</label>
                <select name="stakeholder_id" required>{options}</select>
            </div>
            <div class="form-group">
                <label>Дата-время</label>
                <input type="datetime-local" name="scheduled_at" value="{iv['scheduled_at'] or ''}">
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('interview_detail', id=id)}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать интервью', content=content)

@app.route('/interviews/delete/<int:id>')
def interview_delete(id):
    db = get_db()
    db.execute("UPDATE interview SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
    db.commit()
    db.close()
    flash('Интервью удалено', 'success')
    return redirect(url_for('interviews_list'))

@app.route('/interviews/<int:id>')
def interview_detail(id):
    db = get_db()
    iv = db.execute("""
        SELECT i.*, s.last_name, s.first_name
        FROM interview i JOIN stakeholder s ON i.stakeholder_id=s.id
        WHERE i.id=? AND i.is_deleted=0
    """, (id,)).fetchone()
    if not iv:
        db.close()
        flash('Интервью не найдено', 'error')
        return redirect(url_for('interviews_list'))
    qas = db.execute("SELECT * FROM interview_qa WHERE interview_id=? AND is_deleted=0 ORDER BY id", (id,)).fetchall()
    audios = db.execute("SELECT * FROM interview_audio WHERE interview_id=? AND is_deleted=0 ORDER BY id", (id,)).fetchall()
    segments = db.execute("SELECT * FROM transcript_segment WHERE interview_id=? AND is_deleted=0 ORDER BY start_ms, id", (id,)).fetchall()
    db.close()
    info = [
        ('Интервью', f'#{id}'),
        ('Стейкхолдер', f'<a href="{url_for("stakeholder_detail", id=iv["stakeholder_id"])}">{iv["last_name"]} {iv["first_name"]}</a>'),
        ('Дата-время', iv['scheduled_at'] or '-'),
    ]
    add_qa = f'<a href="{url_for("interview_qa_create", interview_id=id)}" class="btn btn-success">+ Добавить вопрос</a>'
    export_btn = f'<a href="{url_for("interview_export", id=id)}" class="btn btn-success">Экспорт (Markdown)</a>'
    rows_q = [[f'<a href="{url_for("interview_qa_edit", id=q["id"])}">#{q["id"]}</a>', q['question'], q['answer'] or '-',
               '<div style="white-space:nowrap">'
               f'<a href="{url_for("interview_qa_edit", id=q["id"])}" class="btn btn-primary">Изменить</a> '
               f'<a href="{url_for("interview_qa_delete", id=q["id"])}" class="btn btn-danger" onclick="return confirm(\'Удалить?\')">Удалить</a>'
               '</div>'] for q in qas]

    rec_controls = (
        '<button type="button" class="btn btn-danger" id="recStart" onclick="startRec()">● Записать</button> '
        '<button type="button" class="btn btn-secondary" id="recStop" onclick="stopRec()" style="display:none;">■ Стоп</button> '
        '<span id="recStatus" class="muted" style="margin-left:6px;"></span>'
    )
    _rec_script = '''<script>
    var mediaRecorder = null, chunks = [];
    async function startRec() {
      try {
        var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        chunks = [];
        mediaRecorder.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
        mediaRecorder.onstop = async function () {
          var mt = mediaRecorder.mimeType || 'audio/webm';
          var ext = mt.indexOf('mp4') >= 0 ? 'm4a' : 'webm';
          var blob = new Blob(chunks, { type: mt });
          var fd = new FormData();
          fd.append('file', blob, 'record.' + ext);
          await fetch('__UPLOAD__', { method: 'POST', body: fd });
          location.reload();
        };
        mediaRecorder.start();
        document.getElementById('recStatus').textContent = '● запись…';
        document.getElementById('recStart').style.display = 'none';
        document.getElementById('recStop').style.display = 'inline-block';
      } catch (e) {
        document.getElementById('recStatus').textContent = 'Нет доступа к микрофону (нужен HTTPS или localhost)';
      }
    }
    function stopRec() {
      if (mediaRecorder) { mediaRecorder.stop(); document.getElementById('recStop').style.display = 'none';
        document.getElementById('recStatus').textContent = 'сохранение…'; }
    }
    function seek(ms) { var a = document.querySelector('audio.player'); if (a) { a.currentTime = ms / 1000; a.play(); } }
    function busy(form, label) {
      var btn = form.querySelector('button[type="submit"]');
      if (btn) { btn.disabled = true; btn.textContent = label; }
      var st = document.getElementById('recStatus');
      if (st) { st.textContent = label + ' Подождите, повторно нажимать не нужно.'; }
      return true;
    }
    </script>'''.replace('__UPLOAD__', url_for('interview_audio_upload', id=id))
    actions = export_btn + ' ' + rec_controls + _rec_script

    rows_a = [[a['id'], a['original_name'] or a['filename'],
               f'<audio class="player" controls preload="none" style="height:32px; vertical-align:middle;" src="{url_for("interview_audio_get", aid=a["id"])}"></audio>',
               f'<a href="{url_for("interview_audio_download", aid=a["id"])}" class="btn btn-primary">Скачать</a>',
               f'<a href="{url_for("interview_audio_delete", aid=a["id"])}" class="btn btn-danger" onclick="return confirm(\'Удалить?\')">Удалить</a>']
              for a in audios]

    transcript_controls = (
        f'<form method="POST" action="{url_for("interview_transcribe", id=id)}" '
        'onsubmit="return busy(this, \'Распознавание…\');" style="display:inline; margin-left:8px;">'
        '<button type="submit" class="btn btn-warning">Распознать (Whisper)</button></form>'
        f'<a href="{url_for("transcript_edit", id=id)}" class="btn btn-primary" style="margin-left:6px;">Редактировать</a>'
        f'<form method="POST" action="{url_for("transcript_clear", id=id)}" style="display:inline; margin-left:6px;">'
        '<button type="submit" class="btn btn-danger" onclick="return confirm(\'Очистить транскрипт?\')">Очистить</button></form>'
    )
    rows_t = []
    for s in segments:
        rows_t.append([
            f'<a href="#" onclick="seek({s["start_ms"]}); return false;">{fmt_timecode(s["start_ms"])}</a>',
            fmt_timecode(s['end_ms']),
            html.escape(s['speaker'] or '-'),
            html.escape(s['text']),
            f'<a href="{url_for("transcript_segment_delete", id=id, sid=s["id"])}" class="btn btn-danger" onclick="return confirm(\'Удалить?\')">Удалить</a>',
        ])

    return _detail_page('Интервью #' + str(id), info, [
        {'title': 'Вопросы и ответы ' + add_qa, 'headers': ['ID', 'Вопрос', 'Ответ', 'Действия'], 'rows': rows_q},
        {'title': 'Аудиозаписи', 'headers': ['ID', 'Файл', 'Прослушать', 'Скачать', 'Действия'], 'rows': rows_a},
        {'title': 'Транскрипт (посегментные таймкоды) ' + transcript_controls,
         'headers': ['Начало', 'Конец', 'Спикер', 'Текст', 'Действия'], 'rows': rows_t},
    ], actions=actions)

@app.route('/interviews/<int:id>/export')
def interview_export(id):
    db = get_db()
    iv = db.execute("""
        SELECT i.*, s.last_name, s.first_name, s.position
        FROM interview i JOIN stakeholder s ON i.stakeholder_id=s.id
        WHERE i.id=? AND i.is_deleted=0
    """, (id,)).fetchone()
    if not iv:
        db.close()
        flash('Интервью не найдено', 'error')
        return redirect(url_for('interviews_list'))
    qas = db.execute("SELECT * FROM interview_qa WHERE interview_id=? AND is_deleted=0 ORDER BY id", (id,)).fetchall()
    segments = db.execute("SELECT * FROM transcript_segment WHERE interview_id=? AND is_deleted=0 ORDER BY start_ms, id", (id,)).fetchall()
    db.close()
    lines = [f'# Интервью #{id}', '']
    lines.append(f'- **Стейкхолдер:** {iv["last_name"]} {iv["first_name"]}')
    if iv['position']:
        lines.append(f'- **Должность:** {iv["position"]}')
    lines.append(f'- **Дата и время:** {iv["scheduled_at"] or "—"}')
    if qas:
        lines += ['', '## Вопросы и ответы', '']
        for i, q in enumerate(qas, 1):
            lines += [f'### Вопрос {i}', '', f'**Вопрос:** {q["question"]}',
                      '', f'**Ответ:** {q["answer"] or "_(нет ответа)_"}', '']
    if segments:
        lines += ['', '## Транскрипт', '']
        for s in segments:
            who = f' **{s["speaker"]}:**' if s['speaker'] else ''
            lines.append(f'- `[{fmt_timecode(s["start_ms"])}]`{who} {s["text"]}')
        lines.append('')
    md = '\n'.join(lines)
    return send_file(BytesIO(md.encode('utf-8')), mimetype='text/markdown',
                     as_attachment=True, download_name=f'interview_{id}.md')

@app.route('/interview_qa/create', methods=['GET', 'POST'])
def interview_qa_create():
    db = get_db()
    if request.method == 'POST':
        db.execute("INSERT INTO interview_qa (interview_id, question, answer) VALUES (?, ?, ?)",
                   (int(request.form['interview_id']), request.form['question'], request.form.get('answer')))
        db.commit()
        db.close()
        flash('Вопрос добавлен', 'success')
        return redirect(url_for('interview_detail', id=int(request.form['interview_id'])))
    pre_iv = request.args.get('interview_id')
    interviews = db.execute("SELECT * FROM interview WHERE is_deleted=0").fetchall()
    db.close()
    options = ''.join([f'<option value="{i["id"]}" {"selected" if str(i["id"]) == pre_iv else ""}>#{i["id"]}</option>' for i in interviews])
    cancel = url_for('interview_detail', id=int(pre_iv)) if pre_iv else url_for('interviews_list')
    content = f'''
    <div class="card">
        <h2>Новый вопрос-ответ</h2>
        <form method="POST">
            <div class="form-group">
                <label>Интервью</label>
                <select name="interview_id" required>{options}</select>
            </div>
            <div class="form-group">
                <label>Вопрос</label>
                <textarea name="question" required></textarea>
            </div>
            <div class="form-group">
                <label>Ответ</label>
                <textarea name="answer"></textarea>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{cancel}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Новый вопрос-ответ', content=content)

@app.route('/interview_qa/edit/<int:id>', methods=['GET', 'POST'])
def interview_qa_edit(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("UPDATE interview_qa SET interview_id=?, question=?, answer=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                   (int(request.form['interview_id']), request.form['question'], request.form.get('answer'), id))
        db.commit()
        db.close()
        flash('Вопрос-ответ обновлён', 'success')
        return redirect(url_for('interview_detail', id=int(request.form['interview_id'])))
    qa = db.execute("SELECT * FROM interview_qa WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if not qa:
        db.close()
        flash('Вопрос-ответ не найден', 'error')
        return redirect(url_for('interviews_list'))
    interviews = db.execute("SELECT * FROM interview WHERE is_deleted=0").fetchall()
    db.close()
    options = ''.join([f'<option value="{i["id"]}" {"selected" if i["id"] == qa["interview_id"] else ""}>#{i["id"]}</option>' for i in interviews])
    content = f'''
    <div class="card">
        <h2>Редактировать вопрос-ответ</h2>
        <form method="POST">
            <div class="form-group">
                <label>Интервью</label>
                <select name="interview_id" required>{options}</select>
            </div>
            <div class="form-group">
                <label>Вопрос</label>
                <textarea name="question" required>{qa['question']}</textarea>
            </div>
            <div class="form-group">
                <label>Ответ</label>
                <textarea name="answer">{qa['answer'] or ''}</textarea>
            </div>
            <button type="submit" class="btn btn-success">Сохранить</button>
            <a href="{url_for('interview_detail', id=qa['interview_id'])}" class="btn btn-primary">Отмена</a>
        </form>
    </div>
    '''
    return render_template_string(BASE_TEMPLATE, title='Редактировать вопрос-ответ', content=content)

@app.route('/interview_qa/delete/<int:id>')
def interview_qa_delete(id):
    db = get_db()
    qa = db.execute("SELECT interview_id FROM interview_qa WHERE id=? AND is_deleted=0", (id,)).fetchone()
    if qa:
        db.execute("UPDATE interview_qa SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (id,))
        db.commit()
        db.close()
        flash('Вопрос-ответ удалён', 'success')
        return redirect(url_for('interview_detail', id=qa['interview_id']))
    db.close()
    flash('Вопрос-ответ не найден', 'error')
    return redirect(url_for('interviews_list'))


#==================== АУДИО И ТРАНСКРИПТ ИНТЕРВЬЮ ====================

def _audio_path(audio_row):
    return os.path.join(AUDIO_DIR, audio_row['filename'])

@app.route('/interviews/<int:id>/audio', methods=['POST'])
def interview_audio_upload(id):
    f = request.files.get('file')
    if not f or not f.filename:
        flash('Файл не выбран', 'error')
        return redirect(url_for('interview_detail', id=id))
    ext = os.path.splitext(secure_filename(f.filename))[1].lower() or '.webm'
    name = f'interview_{id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}{ext}'
    os.makedirs(AUDIO_DIR, exist_ok=True)
    f.save(os.path.join(AUDIO_DIR, name))
    dur = request.form.get('duration_ms')
    db = get_db()
    db.execute("INSERT INTO interview_audio (interview_id, filename, original_name, mime, duration_ms) VALUES (?, ?, ?, ?, ?)",
               (id, name, f.filename, f.mimetype, int(dur) if dur else None))
    db.commit()
    db.close()
    flash('Аудиозапись загружена', 'success')
    return redirect(url_for('interview_detail', id=id))

@app.route('/interviews/audio/<int:aid>')
def interview_audio_get(aid):
    db = get_db()
    a = db.execute("SELECT * FROM interview_audio WHERE id=? AND is_deleted=0", (aid,)).fetchone()
    db.close()
    if not a or not os.path.exists(_audio_path(a)):
        flash('Аудиозапись не найдена', 'error')
        return redirect(url_for('interviews_list'))
    return send_file(_audio_path(a), mimetype=a['mime'] or 'application/octet-stream', as_attachment=False)

@app.route('/interviews/audio/<int:aid>/download')
def interview_audio_download(aid):
    db = get_db()
    a = db.execute("SELECT * FROM interview_audio WHERE id=? AND is_deleted=0", (aid,)).fetchone()
    db.close()
    if not a or not os.path.exists(_audio_path(a)):
        flash('Аудиозапись не найдена', 'error')
        return redirect(url_for('interviews_list'))
    return send_file(_audio_path(a), mimetype=a['mime'] or 'application/octet-stream', as_attachment=True,
                     download_name=a['original_name'] or a['filename'])

@app.route('/interviews/audio/<int:aid>/delete')
def interview_audio_delete(aid):
    db = get_db()
    a = db.execute("SELECT * FROM interview_audio WHERE id=?", (aid,)).fetchone()
    if a:
        iid = a['interview_id']
        db.execute("UPDATE interview_audio SET is_deleted=1 WHERE id=?", (aid,))
        db.commit()
        db.close()
        try:
            os.remove(_audio_path(a))
        except OSError:
            pass
        flash('Аудиозапись удалена', 'success')
        return redirect(url_for('interview_detail', id=iid))
    db.close()
    flash('Аудиозапись не найдена', 'error')
    return redirect(url_for('interviews_list'))

@app.route('/interviews/<int:id>/transcribe', methods=['POST'])
def interview_transcribe(id):
    db = get_db()
    aid = request.form.get('audio_id')
    if aid:
        a = db.execute("SELECT * FROM interview_audio WHERE id=? AND interview_id=? AND is_deleted=0", (int(aid), id)).fetchone()
    else:
        a = db.execute("SELECT * FROM interview_audio WHERE interview_id=? AND is_deleted=0 ORDER BY id DESC LIMIT 1", (id,)).fetchone()
    db.close()
    if not a:
        flash('Сначала загрузите или запишите аудио', 'error')
        return redirect(url_for('interview_detail', id=id))
    if not os.path.exists(_audio_path(a)):
        flash('Аудиофайл не найден на диске', 'error')
        return redirect(url_for('interview_detail', id=id))
    import time as _time
    _t0 = _time.time()
    print(f'[transcribe] start interview={id} file={a["filename"]} engine checking…', flush=True)
    try:
        import transcribe as stt
        print(f'[transcribe] engine={stt.engine_available()} model={os.environ.get("UPO_STT_MODEL", "small")}', flush=True)
        segs = stt.transcribe(_audio_path(a))
    except Exception as e:
        print(f'[transcribe] ERROR after {_time.time() - _t0:.1f}s: {type(e).__name__}: {e}', flush=True)
        flash(f'Распознавание недоступно: {e}', 'error')
        return redirect(url_for('interview_detail', id=id))
    print(f'[transcribe] done: {len(segs)} segments in {_time.time() - _t0:.1f}s', flush=True)
    db = get_db()
    db.execute("UPDATE transcript_segment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE interview_id=? AND audio_id=?", (id, a['id']))
    for s in segs:
        db.execute("INSERT INTO transcript_segment (interview_id, audio_id, start_ms, end_ms, text) VALUES (?, ?, ?, ?, ?)",
                   (id, a['id'], s['start_ms'], s['end_ms'], s['text']))
    db.commit()
    db.close()
    flash(f'Распознано сегментов: {len(segs)}', 'success')
    return redirect(url_for('interview_detail', id=id))

@app.route('/interviews/<int:id>/transcript/edit')
def transcript_edit(id):
    db = get_db()
    iv = db.execute("SELECT i.*, s.last_name, s.first_name FROM interview i JOIN stakeholder s ON i.stakeholder_id=s.id WHERE i.id=? AND i.is_deleted=0", (id,)).fetchone()
    if not iv:
        db.close()
        flash('Интервью не найдено', 'error')
        return redirect(url_for('interviews_list'))
    segments = db.execute("SELECT * FROM transcript_segment WHERE interview_id=? AND is_deleted=0 ORDER BY start_ms, id", (id,)).fetchall()
    db.close()
    rows = ''.join([
        f'<tr><td>{fmt_timecode(s["start_ms"])}</td><td>{fmt_timecode(s["end_ms"])}</td>'
        f'<td><input type="text" name="speaker_{s["id"]}" value="{html.escape(s["speaker"] or "")}" placeholder="спикер" style="width:130px;"></td>'
        f'<td><input type="text" name="text_{s["id"]}" value="{html.escape(s["text"])}" style="width:100%;"></td></tr>'
        for s in segments])
    content = f'''
    <div class="card">
        <h2>Редактирование транскрипта (интервью #{id})</h2>
        <form method="POST" action="{url_for('transcript_segments_save', id=id)}" onsubmit="return busy(this, 'Сохранение…');">
            <table>
                <thead><tr><th>Начало</th><th>Конец</th><th>Спикер</th><th>Текст</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            <p style="margin-top:12px;">
                <button type="submit" class="btn btn-success">Сохранить все</button>
                <a href="{url_for('interview_detail', id=id)}" class="btn btn-primary">Отмена</a>
            </p>
        </form>
        <script>function busy(f, l) {{ var b = f.querySelector('button[type="submit"]'); if (b) {{ b.disabled = true; b.textContent = l; }} return true; }}</script>
    </div>'''
    return render_template_string(BASE_TEMPLATE, title='Редактирование транскрипта', content=content)

@app.route('/interviews/<int:id>/transcript/save', methods=['POST'])
def transcript_segments_save(id):
    db = get_db()
    n = 0
    for key, val in request.form.items():
        if key.startswith('text_'):
            try:
                sid = int(key[len('text_'):])
            except ValueError:
                continue
            speaker = request.form.get(f'speaker_{sid}') or None
            db.execute("UPDATE transcript_segment SET text=?, speaker=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND interview_id=?",
                       (val, speaker, sid, id))
            n += 1
    db.commit()
    db.close()
    flash(f'Сохранено сегментов: {n}', 'success')
    return redirect(url_for('interview_detail', id=id))

@app.route('/interviews/<int:id>/segment/<int:sid>/delete')
def transcript_segment_delete(id, sid):
    db = get_db()
    db.execute("UPDATE transcript_segment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=? AND interview_id=?", (sid, id))
    db.commit()
    db.close()
    flash('Сегмент удалён', 'success')
    return redirect(url_for('interview_detail', id=id))

@app.route('/interviews/<int:id>/segments/clear', methods=['POST'])
def transcript_clear(id):
    db = get_db()
    db.execute("UPDATE transcript_segment SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE interview_id=?", (id,))
    db.commit()
    db.close()
    flash('Транскрипт очищен', 'success')
    return redirect(url_for('interview_detail', id=id))

