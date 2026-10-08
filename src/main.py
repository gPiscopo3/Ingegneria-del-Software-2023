import os
import sys
import datetime as dt

import requests
from PyQt6.QtCore import Qt, QThread, QLocale, QTranslator, QLibraryInfo, QTimer
from PyQt6.QtWidgets import (QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication,
                             QLineEdit, QFormLayout, QComboBox, QFrame, QLabel, QScrollArea, QFileDialog)

from src import __version__, i18n
from src.i18n import tr
from src.gui.export_dialog import run_export_dialog
from src.gui.graph import (create_graph, GraphWidget, create_graph_communication, create_composite_graph,
                           save_graph_image)
from src.gui.style import apply_theme, palette
from src.gui.widget_calendar import CalendarioApp
from src.gui.worker import DownloadWorker
from src.logic import APICalls, GitHistory
from src.logic.DataManagement import DATA_EXTENSION, save_data, load_data, activity_period

TOKEN_URL = "https://github.com/settings/personal-access-tokens/new"
GIT_URL = "https://git-scm.com/downloads"

# tipi di grafo: chiave (anche nei file esportati) -> chiavi di traduzione di titolo e descrizione
GRAPH_TYPES = {
    "collaboration": ("graph.collaboration.title", "graph.collaboration.description"),
    "communication": ("graph.communication.title", "graph.communication.description"),
    "composite": ("graph.composite.title", "graph.composite.description"),
}

# radice del progetto, o la cartella dei file inclusi quando l'app gira come eseguibile (PyInstaller)
APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXAMPLES_DIR = os.path.join(APP_DIR, "data", "examples")

_qt_translator = None  # traduzioni dei testi standard di Qt (pulsanti Sì/No, dialog dei file)


def install_qt_translator(app: QApplication, code: str):
    global _qt_translator  # pylint: disable=global-statement
    if _qt_translator is not None:
        try:
            app.removeTranslator(_qt_translator)
        except RuntimeError:
            pass  # già distrutto insieme a una QApplication precedente
        _qt_translator = None
    translator = QTranslator()
    if translator.load(f"qtbase_{code}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
        _qt_translator = translator


def data_filter():
    return tr("data.file_filter", extension=DATA_EXTENSION)


def quota_text(rate: dict):
    # es. "2.038/5.000 richieste · rinnovo alle 16:27"
    text = tr("quota.requests", remaining=i18n.format_number(rate['remaining']),
              limit=i18n.format_number(rate['limit']))
    if "reset" in rate:
        text += " · " + tr("quota.reset", time=i18n.format_time(dt.datetime.fromtimestamp(rate['reset'])))
    return text


def section_label(text: str):
    label = QLabel(text.upper())
    label.setObjectName("section")
    return label


def card(*widgets):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setSpacing(8)
    for w in widgets:
        if isinstance(w, QWidget):
            layout.addWidget(w)
        else:
            layout.addLayout(w)
    return frame


class MainViewer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.dark = True
        self.graph_widget = None
        self.current_graph = None  # (grafo, tipo, colori archi), per ridisegnare al cambio tema
        self.graph_context = None  # repository, tipo, intervallo e dati del grafo mostrato (per l'esportazione)

        # dati già scaricati, con la coppia (owner, repo) a cui si riferiscono
        self.files = None
        self.files_key = None
        self.users = None
        self.users_key = None
        # intervallo (inizio, fine) scaricato per ciascuna parte: si riscarica se l'utente ne esce
        self.files_range = None
        self.users_range = None
        self.download_started = None
        self.data_date = None  # data di download (o di salvataggio, se caricati da file) dei dati in memoria

        # periodo coperto dal file caricato: (inizio, fine, periodo di attività o None) e repository a cui si riferisce
        self.data_range = None
        self.data_range_key = None
        self.applied_range_key = None  # repository il cui periodo è applicato al calendario (None = default)

        # download in corso in un thread separato (None se non c'è)
        self.download_thread = None
        self.download_worker = None

        # esito dell'ultima verifica del token (il token resta solo in memoria)
        self.verified_token = None
        self.token_valid = None
        self.last_rate = None  # ultima quota nota, per ridisegnare il badge (es. al cambio di lingua)
        self.git_version = None  # versione di git trovata (None se non disponibile)

        self.setWindowTitle(f'GraphApp {__version__}')
        self.resize(1280, 800)
        self.setMinimumSize(980, 640)

        self.build_ui()
        self.statusBar().showMessage(tr("status.ready"))
        self.update_token_badge()
        self.check_git()
        self.update_data_status()

    # ---------- costruzione interfaccia ----------

    def build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.build_sidebar())
        root.addWidget(self.build_content(), 1)
        # l'interfaccia precedente si distrugge solo dopo l'evento in corso (es. il segnale del selettore di lingua)
        previous = self.takeCentralWidget()
        self.setCentralWidget(central)
        if previous is not None:
            previous.deleteLater()

    def build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(330)
        outer = QVBoxLayout(sidebar)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 22, 20, 20)
        layout.setSpacing(14)

        title = QLabel("GraphApp")
        title.setObjectName("title")
        subtitle = QLabel(tr("app.subtitle"))
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        # lingua e tema in alto, accanto al titolo; le lingue sono i file in src/locales
        self.language_choice = QComboBox()
        self.language_choice.setToolTip(tr("language.tooltip"))
        for code, name in i18n.available_languages().items():
            self.language_choice.addItem(name, code)
        self.language_choice.setCurrentIndex(max(0, self.language_choice.findData(i18n.language())))
        self.language_choice.currentIndexChanged.connect(self.on_language_changed)
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("ghost")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.update_theme_button()
        title_row = QHBoxLayout()
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.language_choice)
        title_row.addWidget(self.theme_button)
        layout.addLayout(title_row)
        layout.addWidget(subtitle)

        # Repository
        self.owner = QLineEdit()
        self.owner.setPlaceholderText(tr("repository.owner_placeholder"))
        self.repo_name = QLineEdit()
        self.repo_name.setPlaceholderText(tr("repository.name_placeholder"))
        repo_form = QFormLayout()
        repo_form.setVerticalSpacing(8)
        repo_form.addRow(tr("repository.owner"), self.owner)
        repo_form.addRow(tr("repository.name"), self.repo_name)
        layout.addWidget(card(section_label(tr("repository.section")), repo_form))

        # Dati: salvataggio e caricamento espliciti dei dati scaricati
        self.load_button = QPushButton(tr("data.load"))
        self.load_button.clicked.connect(self.load_data_file)
        self.save_button = QPushButton(tr("data.save"))
        self.save_button.clicked.connect(self.save_data_file)
        data_row = QHBoxLayout()
        data_row.setSpacing(6)
        data_row.addWidget(self.load_button)
        data_row.addWidget(self.save_button)
        self.data_status = QLabel()
        self.data_status.setObjectName("hint")
        self.data_status.setWordWrap(True)
        layout.addWidget(card(section_label(tr("data.section")), data_row, self.data_status))
        self.owner.textChanged.connect(self.update_data_status)
        self.repo_name.textChanged.connect(self.update_data_status)

        # Autenticazione GitHub
        self.token = QLineEdit()
        self.token.setPlaceholderText(tr("token.placeholder"))
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.textChanged.connect(self.on_token_changed)
        self.show_token_button = QPushButton(tr("token.show"))
        self.show_token_button.setObjectName("ghost")
        self.show_token_button.setCheckable(True)
        self.show_token_button.setFixedWidth(80)
        self.show_token_button.toggled.connect(self.toggle_token_visibility)
        token_row = QHBoxLayout()
        token_row.setSpacing(6)
        token_row.addWidget(self.token, 1)
        token_row.addWidget(self.show_token_button)

        self.verify_button = QPushButton(tr("token.verify"))
        self.verify_button.clicked.connect(self.verify_token)
        self.token_badge = QLabel()
        self.token_badge.setObjectName("badge")
        self.token_badge.setWordWrap(True)
        self.token_link = QLabel()
        self.token_link.setObjectName("hint")
        self.token_link.setOpenExternalLinks(True)
        self.token_link.setWordWrap(True)
        self.update_token_link()
        token_hint = QLabel(tr("token.memory_hint"))
        token_hint.setObjectName("hint")
        token_hint.setWordWrap(True)
        layout.addWidget(card(section_label(tr("token.section")), token_row, self.verify_button,
                              self.token_badge, self.token_link, token_hint))

        # Git: con git i commit si leggono da un clone locale, senza consumare quota API
        self.git_badge = QLabel()
        self.git_badge.setObjectName("badge")
        self.git_badge.setWordWrap(True)
        git_hint = QLabel(tr("git.hint"))
        git_hint.setObjectName("hint")
        git_hint.setWordWrap(True)
        self.git_link = QLabel()
        self.git_link.setObjectName("hint")
        self.git_link.setOpenExternalLinks(True)
        self.update_git_link()
        self.git_button = QPushButton(tr("git.recheck"))
        self.git_button.setObjectName("ghost")
        self.git_button.clicked.connect(self.check_git)
        git_row = QHBoxLayout()
        git_row.addWidget(self.git_link, 1)
        git_row.addWidget(self.git_button)
        layout.addWidget(card(section_label(tr("git.section")), self.git_badge, git_hint, git_row))

        # Tipo di grafo
        self.choice = QComboBox()
        for key, (title_key, _) in GRAPH_TYPES.items():
            self.choice.addItem(tr(title_key), key)
        self.choice_description = QLabel()
        self.choice_description.setObjectName("hint")
        self.choice_description.setWordWrap(True)
        self.choice.currentIndexChanged.connect(self.update_choice_description)
        self.update_choice_description()
        layout.addWidget(card(section_label(tr("graph.section")), self.choice, self.choice_description))

        # Intervallo temporale
        self.calendario_widget = CalendarioApp()
        layout.addWidget(card(section_label(tr("interval.section")), self.calendario_widget))

        self.update_button = QPushButton(tr("action.generate"))
        self.update_button.setObjectName("primary")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(self.on_update_clicked)
        layout.addWidget(self.update_button)

        layout.addStretch(1)
        return sidebar

    def build_content(self):
        content = QWidget()
        content.setObjectName("content")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        self.graph_title = QLabel(tr("graph.none"))
        self.graph_title.setObjectName("graphTitle")
        self.repo_chip = QLabel()
        self.nodes_chip = QLabel()
        self.edges_chip = QLabel()
        header.addWidget(self.graph_title)
        header.addStretch(1)
        for chip in (self.repo_chip, self.nodes_chip, self.edges_chip):
            chip.setObjectName("chip")
            chip.hide()
            header.addWidget(chip)
        # esportazione del grafo mostrato e dei dati grezzi per R, MATLAB e Python
        self.export_button = QPushButton(tr("export.button"))
        self.export_button.setObjectName("ghost")
        self.export_button.setToolTip(tr("export.button_tooltip"))
        self.export_button.clicked.connect(self.export_graph)
        self.export_button.hide()
        header.addWidget(self.export_button)
        layout.addLayout(header)

        self.graph_card = QFrame()
        self.graph_card.setObjectName("graphCard")
        self.graph_layout = QVBoxLayout(self.graph_card)
        self.graph_layout.setContentsMargins(12, 8, 12, 12)
        self.empty_state = self.build_empty_state()
        self.graph_layout.addWidget(self.empty_state)
        layout.addWidget(self.graph_card, 1)
        self.graph_widget = None  # il widget del grafo precedente è stato distrutto con l'interfaccia
        return content

    def build_empty_state(self):
        empty = QWidget()
        layout = QVBoxLayout(empty)
        layout.addStretch(1)
        icon = QLabel("◎")
        icon.setObjectName("emptyIcon")
        title = QLabel(tr("empty.title"))
        title.setObjectName("emptyTitle")
        hint = QLabel(tr("empty.hint"))
        hint.setObjectName("subtitle")
        for w in (icon, title, hint):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(w)
        layout.addStretch(1)
        return empty

    # ---------- lingua ----------

    def on_language_changed(self):
        code = self.language_choice.currentData()
        if code is None or code == i18n.language():
            return
        i18n.set_language(code)
        install_qt_translator(QApplication.instance(), code)
        QTimer.singleShot(0, self.retranslate)  # dopo la fine del segnale: il selettore viene ricostruito

    def retranslate(self):
        # ricostruisce l'interfaccia nella nuova lingua mantenendo ciò che l'utente ha inserito o generato
        owner, repo, token = self.owner.text(), self.repo_name.text(), self.token.text()
        token_shown = self.show_token_button.isChecked()
        choice = self.choice.currentData()
        start = self.calendario_widget.date_edit_inizio.date()
        end = self.calendario_widget.date_edit_fine.date()
        verified_token, token_valid, last_rate = self.verified_token, self.token_valid, self.last_rate
        if self.graph_widget is not None:
            self.graph_widget.release()  # libera subito la figura: il widget viene distrutto con l'interfaccia

        self.build_ui()

        for widget in (self.owner, self.repo_name, self.token):
            widget.blockSignals(True)  # niente reset della verifica del token né dello stato dei dati
        self.owner.setText(owner)
        self.repo_name.setText(repo)
        self.token.setText(token)
        for widget in (self.owner, self.repo_name, self.token):
            widget.blockSignals(False)
        self.show_token_button.setChecked(token_shown)
        self.choice.setCurrentIndex(self.choice.findData(choice))
        self.verified_token, self.token_valid = verified_token, token_valid

        self.applied_range_key = None
        self.apply_data_range()  # limiti e periodo disponibile del file caricato, nella nuova lingua
        self.calendario_widget.date_edit_inizio.setDate(start)
        self.calendario_widget.date_edit_fine.setDate(end)

        self.update_token_badge(last_rate)
        self.update_git_badge()
        self.update_data_status()
        if self.current_graph is not None:
            self.show_graph()
            self.update_graph_header()
        self.statusBar().showMessage(tr("status.ready"))

    # ---------- interazioni ----------

    def update_choice_description(self):
        self.choice_description.setText(tr(GRAPH_TYPES[self.choice.currentData()][1]))

    def toggle_token_visibility(self, visible: bool):
        self.token.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.show_token_button.setText(tr("token.hide") if visible else tr("token.show"))

    def update_token_link(self):
        color = palette(self.dark)["accent"]
        self.token_link.setText(f'<a style="color:{color}; text-decoration:none" href="{TOKEN_URL}">'
                                f'{tr("token.create_link")}</a> {tr("token.create_hint")}')

    def on_token_changed(self):
        self.verified_token = None
        self.token_valid = None
        self.last_rate = None
        self.update_token_badge()

    def set_badge(self, text: str, state: str, badge: QLabel = None):
        badge = badge or self.token_badge
        badge.setText(text)
        badge.setProperty("state", state)
        badge.style().unpolish(badge)
        badge.style().polish(badge)

    def update_git_link(self):
        color = palette(self.dark)["accent"]
        self.git_link.setText(f'<a style="color:{color}; text-decoration:none" href="{GIT_URL}">'
                              f'{tr("git.download_link")}</a>')

    def check_git(self):
        GitHistory.refresh_path()  # git appena installato: non serve riavviare l'app
        self.git_version = GitHistory.git_version()
        self.update_git_badge()

    def update_git_badge(self):
        if self.git_version is not None:
            self.set_badge(tr("git.found", version=self.git_version), "ok", self.git_badge)
            self.git_link.hide()
        else:
            self.set_badge(tr("git.not_found"), "error", self.git_badge)
            self.git_link.show()

    def update_token_badge(self, rate=None):
        if rate is not None:
            self.last_rate = dict(rate)
        if self.token.text().strip() == "":
            if rate is not None:
                self.set_badge(tr("token.none_quota", quota=quota_text(rate)),
                               "error" if rate["remaining"] == 0 else "neutral")
            else:
                self.set_badge(tr("token.none"), "neutral")
        elif self.token_valid is None:
            self.set_badge(tr("token.not_verified"), "neutral")
        elif self.token_valid:
            text = tr("token.authenticated")
            state = "ok"
            if rate is not None:
                text += f" · {quota_text(rate)}"
                if rate["remaining"] == 0:
                    state = "error"  # token valido ma quota esaurita fino al rinnovo
            self.set_badge(text, state)
        else:
            self.set_badge(tr("token.invalid"), "error")

    def verify_token(self):
        token = self.token.text()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            rate = APICalls.get_rate_limit(token)
        except requests.RequestException:
            self.set_badge(tr("token.unreachable"), "error")
            return False
        finally:
            QApplication.restoreOverrideCursor()
        self.verified_token = token
        self.token_valid = rate is not None
        self.update_token_badge(rate)
        return self.token_valid

    def validate_input(self):
        if self.owner.text().strip() == "" or self.repo_name.text().strip() == "":
            QMessageBox.warning(self, tr("validate.missing.title"), tr("validate.missing.text"))
            return False

        if self.calendario_widget.date_edit_inizio.date() > self.calendario_widget.date_edit_fine.date():
            QMessageBox.warning(self, tr("validate.dates.title"), tr("validate.dates.text"))
            return False

        if not self.needs_download():
            return True  # i dati sono già in memoria: il token non serve

        if self.missing_parts()[0] and self.git_version is None:
            answer = QMessageBox.question(self, tr("validate.no_git.title"), tr("validate.no_git.text"))
            if answer != QMessageBox.StandardButton.Yes:
                return False

        if self.token.text().strip() == "":
            answer = QMessageBox.question(self, tr("validate.no_token.title"), tr("validate.no_token.text"))
            return answer == QMessageBox.StandardButton.Yes

        # verifica automatica se il token non è stato ancora verificato (in caso di errore di rete si prosegue)
        if self.verified_token != self.token.text():
            self.verify_token()
        if self.token_valid is False:
            QMessageBox.critical(self, tr("validate.invalid_token.title"), tr("validate.invalid_token.text"))
            return False
        return True

    def current_key(self):
        return self.owner.text().strip(), self.repo_name.text().strip()

    def selected_range(self):
        # intervallo scelto nel calendario: dal giorno «Dal» alle 00:00 al giorno «Al» alle 23:59:59
        qinizio = self.calendario_widget.date_edit_inizio.date()
        qfine = self.calendario_widget.date_edit_fine.date()
        return (dt.datetime(qinizio.year(), qinizio.month(), qinizio.day()),
                dt.datetime(qfine.year(), qfine.month(), qfine.day(), 23, 59, 59))

    def covers(self, data_key, data_range):
        # i dati in memoria valgono per il repository corrente e per tutti i giorni dell'intervallo scelto
        # (confronto per giorni: dati scaricati «fino a oggi» coprono tutta la giornata di oggi)
        if data_key != self.current_key() or data_range is None:
            return False
        start, end = self.selected_range()
        return data_range[0].date() <= start.date() and end.date() <= data_range[1].date()

    def missing_parts(self):
        # (servono le collaborazioni, servono le comunicazioni) per il tipo di grafo e l'intervallo scelti
        choice = self.choice.currentData()
        need_files = choice in ("collaboration", "composite") and not self.covers(self.files_key, self.files_range)
        need_users = choice in ("communication", "composite") and not self.covers(self.users_key, self.users_range)
        return need_files, need_users

    def needs_download(self):
        return any(self.missing_parts())

    def on_update_clicked(self):
        if self.download_thread is not None:  # durante un download il pulsante lo annulla
            APICalls.cancel_event.set()
            self.update_button.setEnabled(False)
            self.update_button.setText(tr("action.cancelling"))
            return
        self.update_graph()

    def update_graph(self):
        if not self.validate_input():
            return
        APICalls.last_rate_limit.clear()
        if self.needs_download():
            self.start_download()
        else:
            self.build_graph()

    # ---------- download in un thread separato ----------

    def start_download(self):
        owner, repo = key = self.current_key()
        need_files, need_users = self.missing_parts()
        start, end = self.selected_range()
        self.download_started = dt.datetime.now().replace(microsecond=0)
        until = None if end.date() >= self.download_started.date() else end  # «Al» = oggi: fino a ora

        self.download_thread = QThread()
        self.download_worker = DownloadWorker(owner, repo, start, until, self.token.text().strip(),
                                              need_files, need_users)
        self.download_worker.moveToThread(self.download_thread)
        self.download_thread.started.connect(self.download_worker.run)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.rate_limited.connect(self.on_rate_limited)
        self.download_worker.part_done.connect(self.on_part_done)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.failed.connect(self.on_download_failed)
        self.download_worker.cancelled.connect(self.on_download_cancelled)

        self.set_busy(True)
        message = tr("status.downloading", repo=f"{owner}/{repo}", start=i18n.format_date(start),
                     end=i18n.format_date(end))
        if (need_files and self.files_key == key) or (need_users and self.users_key == key):
            message = tr("status.redownload") + " " + message
        self.statusBar().showMessage(message)
        self.download_thread.start()

    def set_busy(self, busy: bool):
        for w in (self.owner, self.repo_name, self.token, self.show_token_button, self.verify_button, self.choice,
                  self.calendario_widget, self.load_button, self.git_button, self.language_choice):
            w.setEnabled(not busy)
        self.update_button.setEnabled(True)
        self.update_button.setText(tr("action.cancel_download") if busy else tr("action.generate"))
        self.update_data_status()

    def stop_download_thread(self):
        self.download_thread.quit()
        self.download_thread.wait()
        self.download_worker.deleteLater()
        self.download_thread.deleteLater()
        self.download_thread = None
        self.download_worker = None
        self.set_busy(False)

    def on_download_progress(self, message: str):
        if not APICalls.cancel_event.is_set():
            owner, repo = self.download_worker.owner, self.download_worker.repo
            self.statusBar().showMessage(f"{owner}/{repo} · {message}")
            rate = dict(APICalls.last_rate_limit)
            if "remaining" in rate and "limit" in rate and (self.token_valid or self.token.text().strip() == ""):
                self.update_token_badge(rate)

    def on_rate_limited(self, seconds: int):
        resume = i18n.format_time(dt.datetime.now() + dt.timedelta(seconds=seconds))
        self.statusBar().showMessage(tr("status.rate_limited", time=resume))

    def on_part_done(self, kind: str, data):
        key = (self.download_worker.owner, self.download_worker.repo)
        covered = (self.download_worker.starting_date, self.download_worker.until or self.download_started)
        if kind == "files":
            self.files, self.files_key, self.files_range = data, key, covered
        else:
            self.users, self.users_key, self.users_range = data, key, covered
        self.data_date = dt.datetime.now().replace(microsecond=0)
        self.update_data_status()

    def on_download_finished(self):
        self.stop_download_thread()
        self.build_graph()

    def on_download_failed(self, error: str):
        self.stop_download_thread()
        QMessageBox.critical(self, tr("error.title"), tr("error.download", error=error))
        self.statusBar().showMessage(tr("status.download_error"))

    def on_download_cancelled(self):
        self.stop_download_thread()
        self.statusBar().showMessage(tr("status.download_cancelled"))

    def closeEvent(self, event):  # pylint: disable=invalid-name
        if self.download_thread is not None:
            APICalls.cancel_event.set()
            self.download_thread.quit()
            self.download_thread.wait()
        super().closeEvent(event)

    def build_graph(self):
        # costruisce il grafo con i dati già in memoria (nessuna chiamata alle API)
        owner, repo = key = self.current_key()
        choice = self.choice.currentData()
        data_inizio, data_fine = self.selected_range()
        files = self.files if self.files_key == key else None
        users = self.users if self.users_key == key else None

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            edge_color = None
            if choice == "collaboration":
                g, _ = create_graph(owner, repo, data_inizio, "", data_inizio, data_fine, files)
                flag = 1
            elif choice == "communication":
                g, _ = create_graph_communication(owner, repo, data_inizio, "", data_inizio, data_fine, users)
                flag = 2
            else:
                g, _, _, edge_color = create_composite_graph(owner, repo, data_inizio, "", data_inizio,
                                                             data_fine, files, users)
                flag = 3
        except Exception as e:  # pylint: disable=broad-except
            QMessageBox.critical(self, tr("error.title"), tr("error.graph", error=e))
            self.statusBar().showMessage(tr("status.graph_error"))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.current_graph = (g, flag, edge_color, None)  # disposizione dei nodi calcolata al primo disegno
        self.show_graph()
        pos = self.current_graph[3]  # stessa disposizione del grafo mostrato anche nell'immagine esportata

        def draw_image(path, dark=False):
            # titolo nella lingua attiva al momento dell'esportazione
            title = tr("image.title", repo=f"{owner}/{repo}", graph=tr(GRAPH_TYPES[choice][0]),
                       start=i18n.format_date(data_inizio), end=i18n.format_date(data_fine))
            save_graph_image(path, g, flag, edge_color, pos, title, dark)

        # contesto del grafo mostrato: l'esportazione resta coerente anche se poi si cambia il calendario
        self.graph_context = {"owner": owner, "repo": repo, "kind": choice, "start": data_inizio,
                              "end": data_fine, "files": files, "users": users, "draw_image": draw_image}
        self.update_graph_header()
        self.show_rate_limit_status(data_inizio, data_fine)

    def update_graph_header(self):
        g, context = self.current_graph[0], self.graph_context
        self.graph_title.setText(tr(GRAPH_TYPES[context["kind"]][0]))
        self.repo_chip.setText(f"{context['owner']}/{context['repo']}")
        self.nodes_chip.setText(tr("graph.developers", count=i18n.format_number(g.number_of_nodes())))
        self.edges_chip.setText(tr("graph.links", count=i18n.format_number(g.number_of_edges())))
        for chip in (self.repo_chip, self.nodes_chip, self.edges_chip):
            chip.show()
        self.export_button.show()

    def export_graph(self):
        if self.graph_context is None:
            return
        result = run_export_dialog(self.graph_context, self)
        if result:
            created, count = result
            folder = os.path.dirname(created[0])
            if created[0].endswith(".zip"):
                self.statusBar().showMessage(tr("status.exported_zip", name=os.path.basename(created[0]),
                                                count=count, folder=folder))
            else:
                self.statusBar().showMessage(tr("status.exported_one" if count == 1 else "status.exported_many",
                                                count=count, folder=folder))

    def show_graph(self):
        if self.current_graph is None:
            return
        if self.graph_widget is not None:
            self.graph_layout.removeWidget(self.graph_widget)
            self.graph_widget.release()  # libera subito figura e artisti del grafo precedente
            self.graph_widget.deleteLater()
            self.graph_widget = None
        self.empty_state.hide()
        g, flag, edge_color, pos = self.current_graph
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.graph_widget = GraphWidget(g, flag, edge_color, self.dark, pos)
        finally:
            QApplication.restoreOverrideCursor()
        # la disposizione si riusa al cambio tema invece di ricalcolarla
        self.current_graph = (g, flag, edge_color, self.graph_widget.pos)
        self.graph_layout.addWidget(self.graph_widget)

    def show_rate_limit_status(self, start: dt.datetime, end: dt.datetime):
        message = tr("status.interval", start=i18n.format_date(start), end=i18n.format_date(end))
        rate = APICalls.last_rate_limit
        if "remaining" in rate and "limit" in rate:
            message += "   ·   " + tr("status.quota", quota=quota_text(rate))
            if self.token_valid or self.token.text().strip() == "":
                self.update_token_badge(dict(rate))
        else:
            message += "   ·   " + tr("status.data_in_memory")
        self.statusBar().showMessage(message)

    # ---------- salvataggio e caricamento dei dati ----------

    def apply_data_range(self, force: bool = False):
        # limita il calendario al periodo del file caricato, solo se si sta guardando quel repository
        key = self.current_key() if self.data_range is not None and self.data_range_key == self.current_key() else None
        if key == self.applied_range_key and not force:
            return  # non sovrascrive a ogni tasto le date scelte dall'utente
        self.applied_range_key = key
        if key is None:
            self.calendario_widget.reset_range()
            return
        start, end, activity = self.data_range
        self.calendario_widget.set_range(start, end)
        hint = tr("interval.available", start=i18n.format_date(start), end=i18n.format_date(end))
        if activity is not None:
            hint += " · " + tr("interval.activity", start=i18n.format_date(activity[0]),
                               end=i18n.format_date(activity[1]))
        self.calendario_widget.set_hint(hint)

    def update_data_status(self):
        self.apply_data_range()
        key = self.current_key()
        has_files = self.files is not None and self.files_key == key
        has_users = self.users is not None and self.users_key == key
        self.save_button.setEnabled((has_files or has_users) and self.download_thread is None)
        if not (has_files or has_users):
            self.data_status.setText(tr("data.status_empty"))
            return

        def part(name, present, data_range):
            if not present:
                return f"{name} ✕"
            if data_range is None:
                return f"{name} ✓"
            return f"{name} ✓ {i18n.format_date(data_range[0])}–{i18n.format_date(data_range[1])}"

        text = (f"{key[0]}/{key[1]} · {part(tr('data.collaborations'), has_files, self.files_range)} · "
                f"{part(tr('data.communications'), has_users, self.users_range)}")
        if self.data_date is not None:
            text += " · " + tr("data.date", date=i18n.format_datetime(self.data_date))
        self.data_status.setText(text)

    def save_data_file(self):
        owner, repo = self.current_key()
        files = self.files if self.files_key == (owner, repo) else None
        users = self.users if self.users_key == (owner, repo) else None
        files_range = self.files_range if files is not None else None
        users_range = self.users_range if users is not None else None
        default = os.path.join(os.path.expanduser("~"), f"{owner}_{repo}{DATA_EXTENSION}")
        path, _ = QFileDialog.getSaveFileName(self, tr("data.save_title"), default, data_filter())
        if not path:
            return
        if not path.endswith(DATA_EXTENSION):
            path += DATA_EXTENSION
        try:
            starts = [r[0] for r in (files_range, users_range) if r is not None]
            save_data(path, owner, repo, min(starts) if starts else self.selected_range()[0], files, users,
                      files_range, users_range)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, tr("error.title"), tr("error.save", error=e))
            return
        self.statusBar().showMessage(tr("status.saved", repo=f"{owner}/{repo}", path=path))

    def load_data_file(self):
        start_dir = EXAMPLES_DIR if os.path.isdir(EXAMPLES_DIR) else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, tr("data.load_title"), start_dir, data_filter())
        if not path:
            return
        try:
            data = load_data(path)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, tr("error.title"), tr("error.load", error=e))
            return

        key = (data["owner"], data["repo"])
        # i dati assenti nel file vengono scartati, per non mescolarli con quelli di un altro repository
        self.files, self.files_key = (data["files"], key) if data["files"] is not None else (None, None)
        self.users, self.users_key = (data["users"], key) if data["users"] is not None else (None, None)
        self.files_range, self.users_range = data["files_range"], data["users_range"]
        self.data_date = data.get("saved_at")

        # periodo coperto: dall'inizio del download alla sua fine (nei file meno recenti, il salvataggio)
        start, end = data.get("starting_date"), data.get("ending_date")
        if isinstance(start, dt.datetime) and isinstance(end, dt.datetime) and start <= end:
            self.data_range = (start, end, activity_period(data["files"], data["users"]))
            self.data_range_key = key
        else:
            self.data_range = self.data_range_key = None

        self.owner.setText(data["owner"])
        self.repo_name.setText(data["repo"])
        self.apply_data_range(force=True)
        self.update_data_status()
        message = tr("status.loaded", repo=f"{key[0]}/{key[1]}", file=os.path.basename(path))
        if self.data_range is not None:
            message += ": " + tr("status.loaded_range", start=i18n.format_date(start), end=i18n.format_date(end))
        self.statusBar().showMessage(message)

        # se il file contiene i dati per il tipo di grafo scelto, lo genera subito
        if not self.needs_download():
            self.update_graph()

    def update_theme_button(self):
        # solo l'icona, per lasciare spazio al selettore di lingua; il testo è nel tooltip
        self.theme_button.setText("☀" if self.dark else "☾")
        self.theme_button.setToolTip(tr("theme.light") if self.dark else tr("theme.dark"))

    def toggle_theme(self):
        self.dark = not self.dark
        apply_theme(QApplication.instance(), self.dark)
        self.update_theme_button()
        self.update_token_link()
        self.update_git_link()
        self.show_graph()


def main():
    app = QApplication(sys.argv)
    # lingua del sistema, se tradotta (file in src/locales), altrimenti inglese
    i18n.set_language(i18n.detect_language(QLocale.system().name()))
    install_qt_translator(app, i18n.language())
    apply_theme(app, True)
    viewer = MainViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
