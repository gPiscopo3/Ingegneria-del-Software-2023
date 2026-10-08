import ast
import glob
import json
import os
import re
import string
from datetime import datetime

import pytest

from src import i18n

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "src")
KEY_PATTERN = re.compile(r"^[a-z_]+(\.[a-z_]+)+$")
ORIGINAL_DIR = i18n.LOCALES_DIR
LOCALE_FILES = sorted(glob.glob(os.path.join(ORIGINAL_DIR, "*.json")))


def load(path):
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def reference():
    return load(os.path.join(ORIGINAL_DIR, i18n.FALLBACK + ".json"))


def source_trees():
    for path in glob.glob(os.path.join(SRC_DIR, "**", "*.py"), recursive=True):
        with open(path, encoding="utf-8") as fp:
            yield path, ast.parse(fp.read())


def tr_keys():
    # chiavi letterali passate a tr(...), anche dentro un'espressione condizionale
    keys = set()
    for path, tree in source_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "tr" \
                    and node.args:
                argument = node.args[0]
                values = [argument.body, argument.orelse] if isinstance(argument, ast.IfExp) else [argument]
                keys.update((v.value, path) for v in values if isinstance(v, ast.Constant))
    return keys


def string_constants():
    return {node.value for _, tree in source_trees() for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)}


@pytest.fixture(autouse=True)
def restore_language():
    yield
    i18n.set_locales_dir(ORIGINAL_DIR)
    i18n.set_language(i18n.FALLBACK)


def test_at_least_italian_and_english():
    assert {"it", "en"} <= set(i18n.available_languages())


# i controlli seguenti valgono per ogni file di lingua presente: una lingua nuova è controllata senza nuovo codice
@pytest.mark.parametrize("path", LOCALE_FILES, ids=os.path.basename)
def test_locale_meta_complete(path):
    meta = load(path)["meta"]
    assert set(i18n.META_FIELDS) <= set(meta)
    datetime(2023, 11, 15, 16, 27).strftime(meta["date_format"] + " " + meta["time_format"])
    assert "yyyy" in meta["qt_date_format"]


@pytest.mark.parametrize("path", LOCALE_FILES, ids=os.path.basename)
def test_locale_same_keys_as_reference(path):
    messages, expected = load(path)["messages"], reference()["messages"]
    assert sorted(set(expected) - set(messages)) == [], "chiavi mancanti"
    assert sorted(set(messages) - set(expected)) == [], "chiavi in più"


@pytest.mark.parametrize("path", LOCALE_FILES, ids=os.path.basename)
def test_locale_same_placeholders(path):
    messages, expected = load(path)["messages"], reference()["messages"]
    wrong = [key for key, text in messages.items() if placeholders(text) != placeholders(expected.get(key, ""))]
    assert wrong == []


def test_every_key_used_in_code_exists():
    messages = reference()["messages"]
    missing = sorted({f"{key} ({os.path.basename(path)})" for key, path in tr_keys()
                      if KEY_PATTERN.match(key) and key not in messages})
    assert missing == []


def test_no_unused_keys():
    used = string_constants()
    assert sorted(key for key in reference()["messages"] if key not in used) == []


def test_detect_language():
    assert i18n.detect_language("it_IT") == "it"
    assert i18n.detect_language("en_US") == "en"
    assert i18n.detect_language("xx_XX") == i18n.FALLBACK
    assert i18n.detect_language("") == i18n.FALLBACK


def test_tr_and_formats():
    i18n.set_language("it")
    assert i18n.tr("action.generate") == "Genera grafo"
    assert i18n.tr("graph.developers", count=3) == "3 sviluppatori"
    assert i18n.format_date(datetime(2023, 11, 15)) == "15/11/2023"
    assert i18n.format_number(5000) == "5.000"
    i18n.set_language("en")
    assert i18n.tr("action.generate") == "Generate graph"
    assert i18n.format_date(datetime(2023, 11, 15)) == "2023-11-15"
    assert i18n.format_number(5000) == "5,000"
    assert i18n.tr("chiave.inesistente") == "chiave.inesistente"  # mai un errore per una chiave mancante


def test_new_language_needs_only_a_file(tmp_path):
    # una lingua aggiunta come file viene scoperta e usata senza toccare il codice
    for path in LOCALE_FILES:
        (tmp_path / os.path.basename(path)).write_text(open(path, encoding="utf-8").read(), encoding="utf-8")
    german = reference()
    german["meta"].update(name="Deutsch", date_format="%d.%m.%Y", qt_date_format="dd.MM.yyyy",
                          thousands_separator=".")
    german["messages"]["action.generate"] = "Graph erstellen"
    (tmp_path / "de.json").write_text(json.dumps(german), encoding="utf-8")

    i18n.set_locales_dir(str(tmp_path))
    assert i18n.available_languages()["de"] == "Deutsch"
    assert i18n.detect_language("de_DE") == "de"
    i18n.set_language("de")
    assert i18n.tr("action.generate") == "Graph erstellen"
    assert i18n.format_date(datetime(2023, 11, 15)) == "15.11.2023"
    assert i18n.tr("graph.developers", count=2) == "2 developers"  # testo non tradotto: come nel file di partenza


def test_missing_key_falls_back_to_english(tmp_path):
    for path in LOCALE_FILES:
        (tmp_path / os.path.basename(path)).write_text(open(path, encoding="utf-8").read(), encoding="utf-8")
    partial = {"meta": dict(reference()["meta"], name="Parziale"), "messages": {}}
    (tmp_path / "xx.json").write_text(json.dumps(partial), encoding="utf-8")
    i18n.set_locales_dir(str(tmp_path))
    i18n.set_language("xx")
    assert i18n.tr("action.generate") == "Generate graph"
