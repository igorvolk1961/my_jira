"""
Локальная транскрибация интервью (CPU, без GPU).

Модуль опционален: приложение работает и без него. Если ни одна библиотека
не установлена, transcribe() вернёт понятную ошибку, а не упадёт.

Установка (одна из):
    uv sync --extra transcription            # faster-whisper
    pip install faster-whisper               # быстрее на CPU, int8
    pip install pywhispercpp                 # движок whisper.cpp (как в Buzz)

Может потребоваться ffmpeg для декодирования аудио.
"""

import os


class TranscriptionUnavailable(RuntimeError):
    pass


def engine_available():
    """Возвращает имя доступного движка или None."""
    try:
        import faster_whisper  # noqa: F401
        return 'faster-whisper'
    except Exception:
        pass
    try:
        import pywhispercpp  # noqa: F401
        return 'pywhispercpp'
    except Exception:
        pass
    return None


def _transcribe_faster_whisper(path, model, language):
    from faster_whisper import WhisperModel
    wm = WhisperModel(model, device='cpu', compute_type='int8')
    segments, _info = wm.transcribe(path, language=language, vad_filter=True)
    out = []
    for s in segments:
        out.append({
            'start_ms': int((s.start or 0) * 1000),
            'end_ms': int((s.end or 0) * 1000),
            'text': (s.text or '').strip(),
        })
    return out


def _transcribe_pywhispercpp(path, model, language):
    from pywhispercpp.model import Model
    m = Model(model, language=language)
    out = []
    for s in m.transcribe(path):
        out.append({
            'start_ms': int((s.t0 or 0) * 10),   # pywhispercpp: t0/t1 в 10-мс тиках
            'end_ms': int((s.t1 or 0) * 10),
            'text': (s.text or '').strip(),
        })
    return out


def transcribe(path, model=None, language=None):
    """Транскрибирует аудиофайл. Возвращает список {start_ms, end_ms, text}."""
    model = model or os.environ.get('UPO_STT_MODEL', 'small')
    language = language or os.environ.get('UPO_STT_LANGUAGE', 'ru')
    engine = engine_available()
    if engine is None:
        raise TranscriptionUnavailable(
            'Движок распознавания не установлен. Установите faster-whisper '
            '("uv sync --extra transcription") или pywhispercpp, и ffmpeg для декодирования.'
        )
    if engine == 'faster-whisper':
        segs = _transcribe_faster_whisper(path, model, language)
    else:
        segs = _transcribe_pywhispercpp(path, model, language)
    return [s for s in segs if s['text']]


def diarize(path):
    """Опциональная диаризация: список {start_ms, end_ms, speaker}.

    По умолчанию не реализована (возвращает []). Точка расширения:
      - SpeechBrain (ECAPA-TDNN) + webrtcvad + кластеризация (CPU, без токена);
      - pyannote.audio (лучшее качество, нужен бесплатный HF-токен, медленно на CPU).
    """
    return []
