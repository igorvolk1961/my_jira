"""Локальная транскрибация интервью (опциональный движок).

Модуль самодостаточен: приложение работает и без установленных библиотек
распознавания. Если движок недоступен, :func:`transcribe` поднимает
:class:`TranscriptionUnavailable` с понятным сообщением, а не падает.

Установка (одна из):
    uv sync --extra transcription   # faster-whisper (CPU, int8)
    pip install pywhispercpp        # whisper.cpp (как в Buzz)

Для декодирования аудио может потребоваться ffmpeg.
"""

import os
from typing import Any

Segment = dict[str, Any]


class TranscriptionUnavailable(RuntimeError):
    """Движок распознавания недоступен."""


def engine_available() -> str | None:
    """Возвращает имя доступного движка или None."""
    try:
        import faster_whisper  # noqa: F401

        return "faster-whisper"
    except Exception:
        pass
    try:
        import pywhispercpp  # noqa: F401

        return "pywhispercpp"
    except Exception:
        pass
    return None


_MODELS: dict[tuple[str, str], Any] = {}


def _faster_whisper_model(model: str, compute_type: str) -> Any:
    """Кэширует модель: повторные распознавания не перезагружают её с диска."""
    key = (model, compute_type)
    instance = _MODELS.get(key)
    if instance is None:
        from faster_whisper import WhisperModel

        instance = WhisperModel(model, device="cpu", compute_type=compute_type)
        _MODELS[key] = instance
    return instance


def _transcribe_faster_whisper(path: str, model: str, language: str | None) -> list[Segment]:
    wm = _faster_whisper_model(model, "int8")
    segments, _info = wm.transcribe(path, language=language, vad_filter=True)
    out: list[Segment] = []
    for segment in segments:
        out.append(
            {
                "start_ms": int((segment.start or 0) * 1000),
                "end_ms": int((segment.end or 0) * 1000),
                "text": (segment.text or "").strip(),
            }
        )
    return out


def _transcribe_pywhispercpp(path: str, model: str, language: str | None) -> list[Segment]:
    from pywhispercpp.model import Model

    engine = Model(model, language=language)
    out: list[Segment] = []
    for segment in engine.transcribe(path):
        out.append(
            {
                "start_ms": int((segment.t0 or 0) * 10),
                "end_ms": int((segment.t1 or 0) * 10),
                "text": (segment.text or "").strip(),
            }
        )
    return out


def transcribe(path: str, model: str | None = None, language: str | None = None) -> list[Segment]:
    """Транскрибирует аудиофайл. Возвращает список {start_ms, end_ms, text}."""
    model = model or os.environ.get("UPO_STT_MODEL", "small")
    language = language or os.environ.get("UPO_STT_LANGUAGE", "ru")
    engine = engine_available()
    if engine is None:
        raise TranscriptionUnavailable(
            "Движок распознавания не установлен. Установите faster-whisper "
            '("uv sync --extra transcription") или pywhispercpp, и ffmpeg для декодирования.'
        )
    if engine == "faster-whisper":
        segments = _transcribe_faster_whisper(path, model, language)
    else:
        segments = _transcribe_pywhispercpp(path, model, language)
    return [segment for segment in segments if segment["text"]]
