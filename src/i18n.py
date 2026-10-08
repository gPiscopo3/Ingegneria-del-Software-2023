import json
import os
from datetime import datetime
from typing import Dict, Optional

# traduzioni dell'interfaccia: ogni lingua è un file src/locales/<codice>.json con "meta" (nome e formati) e
# "messages" (chiave -> testo). Per aggiungere una lingua basta aggiungere il file: nessun codice da scrivere.

LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
FALLBACK = "en"  # lingua usata se quella di sistema non è tradotta, e per le chiavi mancanti
META_FIELDS = ("name", "date_format", "qt_date_format", "time_format", "thousands_separator")

_catalogs: Dict[str, dict] = {}
_current = FALLBACK


def set_locales_dir(path: str):
    # cartella delle lingue (i test ne usano una temporanea)
    global LOCALES_DIR, _current  # pylint: disable=global-statement
    LOCALES_DIR = path
    _catalogs.clear()
    _current = FALLBACK


def _load():
    if not _catalogs and os.path.isdir(LOCALES_DIR):
        for name in sorted(os.listdir(LOCALES_DIR)):
            code, extension = os.path.splitext(name)
            if extension == ".json":
                with open(os.path.join(LOCALES_DIR, name), encoding="utf-8") as fp:
                    _catalogs[code] = json.load(fp)
    return _catalogs


# {codice: nome nativo}, ordinate per nome (es. {"en": "English", "it": "Italiano"})
def available_languages() -> Dict[str, str]:
    catalogs = _load()
    return dict(sorted(((code, c["meta"]["name"]) for code, c in catalogs.items()), key=lambda item: item[1]))


# lingua da usare per un nome di locale di sistema (es. "it_IT" -> "it"); se non tradotta, FALLBACK
def detect_language(locale_name: str) -> str:
    prefix = (locale_name or "").replace("-", "_").split("_")[0].lower()
    return prefix if prefix in _load() else FALLBACK


def set_language(code: str):
    global _current  # pylint: disable=global-statement
    _current = code if code in _load() else FALLBACK


def language() -> str:
    return _current


def _catalog(code: str) -> dict:
    return _load().get(code, {"meta": {}, "messages": {}})


def meta(field: str) -> str:
    value = _catalog(_current)["meta"].get(field)
    return value if value is not None else _catalog(FALLBACK)["meta"][field]


# testo della chiave nella lingua corrente, con i segnaposto {nome} sostituiti dai valori passati
def tr(key: str, **values) -> str:
    text: Optional[str] = _catalog(_current)["messages"].get(key)
    if text is None:
        text = _catalog(FALLBACK)["messages"].get(key, key)
    try:
        return text.format(**values) if values else text
    except (KeyError, IndexError, ValueError):
        return text


def format_date(value: datetime) -> str:
    return value.strftime(meta("date_format"))


def format_time(value: datetime) -> str:
    return value.strftime(meta("time_format"))


def format_datetime(value: datetime) -> str:
    return format_date(value) + " " + format_time(value)


def format_number(n: int) -> str:
    return f"{n:,}".replace(",", meta("thousands_separator"))


def qt_date_format() -> str:
    return meta("qt_date_format")
