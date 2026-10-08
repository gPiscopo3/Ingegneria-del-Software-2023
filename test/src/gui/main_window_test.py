import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QDate  # pylint: disable=wrong-import-position
from PyQt6.QtWidgets import QApplication  # pylint: disable=wrong-import-position

from src import i18n  # pylint: disable=wrong-import-position
from src.logic.DataManagement import load_data  # pylint: disable=wrong-import-position
from src.main import MainViewer  # pylint: disable=wrong-import-position

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "examples", "apache_commons-io.graphapp")
APP = QApplication.instance() or QApplication([])  # una sola QApplication per tutti i test, come nell'app


@pytest.fixture(name="window")
def fixture_window():
    app = APP
    i18n.set_language("it")
    window = MainViewer()
    yield window
    window.close()
    window.deleteLater()
    app.processEvents()
    i18n.set_language(i18n.FALLBACK)


def switch_language(window, code):
    window.language_choice.setCurrentIndex(window.language_choice.findData(code))
    QApplication.processEvents()  # l'interfaccia si ricostruisce alla fine del segnale del selettore


def test_language_selector_lists_available_languages(window):
    codes = [window.language_choice.itemData(i) for i in range(window.language_choice.count())]
    assert set(codes) == set(i18n.available_languages())
    assert window.language_choice.currentData() == "it"
    assert window.update_button.text() == "Genera grafo"


def test_switch_language_keeps_user_input(window):
    window.owner.setText("apache")
    window.repo_name.setText("commons-io")
    window.token.setText("segreto")
    window.choice.setCurrentIndex(window.choice.findData("communication"))
    window.calendario_widget.date_edit_inizio.setDate(QDate(2024, 1, 10))
    window.calendario_widget.date_edit_fine.setDate(QDate(2024, 2, 20))

    switch_language(window, "en")

    assert i18n.language() == "en"
    assert window.update_button.text() == "Generate graph"
    assert window.token_badge.text() == "Token not verified yet"
    assert (window.owner.text(), window.repo_name.text(), window.token.text()) == ("apache", "commons-io", "segreto")
    assert window.choice.currentData() == "communication"
    assert window.choice.currentText() == "Communication graph"
    assert window.calendario_widget.date_edit_inizio.date() == QDate(2024, 1, 10)
    assert window.calendario_widget.date_edit_fine.date() == QDate(2024, 2, 20)
    assert window.calendario_widget.date_edit_inizio.displayFormat() == "yyyy-MM-dd"

    switch_language(window, "it")
    assert window.update_button.text() == "Genera grafo"
    assert window.owner.text() == "apache"


def test_switch_language_keeps_graph(window):
    data = load_data(EXAMPLE)
    key = (data["owner"], data["repo"])
    window.files, window.files_key, window.users, window.users_key = data["files"], key, data["users"], key
    window.files_range, window.users_range = data["files_range"], data["users_range"]
    window.owner.setText(key[0])
    window.repo_name.setText(key[1])
    window.choice.setCurrentIndex(window.choice.findData("composite"))
    window.calendario_widget.date_edit_inizio.setDate(QDate(2023, 11, 15))
    window.calendario_widget.date_edit_fine.setDate(QDate(2023, 12, 18))
    window.build_graph()
    nodes = window.current_graph[0].number_of_nodes()

    switch_language(window, "en")

    assert window.graph_widget is not None
    assert window.graph_title.text() == "Composite graph"
    assert window.nodes_chip.text() == f"{nodes} developers"
    assert not window.export_button.isHidden()
    assert window.graph_context["kind"] == "composite"
