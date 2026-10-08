import os
import sys
import datetime as dt

import requests
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import (QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication,
                             QLineEdit, QFormLayout, QComboBox, QFrame, QLabel, QScrollArea, QFileDialog)

from src.gui.export_dialog import run_export_dialog
from src.gui.graph import create_graph, GraphWidget, create_graph_communication, create_composite_graph
from src.gui.style import apply_theme, palette
from src.gui.widget_calendar import CalendarioApp
from src.gui.worker import DownloadWorker
from src.logic import APICalls, GitHistory
from src.logic.DataManagement import DATA_EXTENSION, save_data, load_data, activity_period

TOKEN_URL = "https://github.com/settings/personal-access-tokens/new"
GIT_URL = "https://git-scm.com/downloads"

GRAPH_TYPES = {
    "collaborazioni": ("Grafo delle collaborazioni",
                       "Collega gli sviluppatori che hanno modificato gli stessi file. "
                       "Il peso indica quanti file hanno in comune."),
    "comunicazioni": ("Grafo delle comunicazioni",
                      "Grafo diretto: un arco A → B indica che A ha risposto a B in issue, "
                      "pull request, review o commenti."),
    "composito": ("Grafo composito",
                  "Sovrappone i due grafi: blu le collaborazioni, rosso le comunicazioni, "
                  "viola le coppie presenti in entrambi."),
}

DATA_FILTER = f"Dati GraphApp (*{DATA_EXTENSION})"
EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "examples")


def format_number(n: int):
    return f"{n:,}".replace(",", ".")


def quota_text(rate: dict):
    # es. "2.038/5.000 richieste · rinnovo alle 16:27"
    text = f"{format_number(rate['remaining'])}/{format_number(rate['limit'])} richieste"
    if "reset" in rate:
        text += f" · rinnovo alle {dt.datetime.fromtimestamp(rate['reset']).strftime('%H:%M')}"
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
        self.git_version = None  # versione di git trovata (None se non disponibile)

        self.setWindowTitle('GraphApp')
        self.resize(1280, 800)
        self.setMinimumSize(980, 640)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.build_sidebar())
        root.addWidget(self.build_content(), 1)

        self.statusBar().showMessage("Pronto")
        self.update_token_badge()
        self.check_git()
        self.update_data_status()

    # ---------- costruzione interfaccia ----------

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
        subtitle = QLabel("Analisi delle interazioni tra gli sviluppatori di un repository GitHub")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Repository
        self.owner = QLineEdit()
        self.owner.setPlaceholderText("es. apache")
        self.repo_name = QLineEdit()
        self.repo_name.setPlaceholderText("es. commons-io")
        repo_form = QFormLayout()
        repo_form.setVerticalSpacing(8)
        repo_form.addRow("Owner", self.owner)
        repo_form.addRow("Nome", self.repo_name)
        layout.addWidget(card(section_label("Repository"), repo_form))

        # Dati: salvataggio e caricamento espliciti dei dati scaricati
        self.load_button = QPushButton("Carica dati…")
        self.load_button.clicked.connect(self.load_data_file)
        self.save_button = QPushButton("Salva dati…")
        self.save_button.clicked.connect(self.save_data_file)
        data_row = QHBoxLayout()
        data_row.setSpacing(6)
        data_row.addWidget(self.load_button)
        data_row.addWidget(self.save_button)
        self.data_status = QLabel()
        self.data_status.setObjectName("hint")
        self.data_status.setWordWrap(True)
        layout.addWidget(card(section_label("Dati"), data_row, self.data_status))
        self.owner.textChanged.connect(self.update_data_status)
        self.repo_name.textChanged.connect(self.update_data_status)

        # Autenticazione GitHub
        self.token = QLineEdit()
        self.token.setPlaceholderText("Personal access token")
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.textChanged.connect(self.on_token_changed)
        self.show_token_button = QPushButton("Mostra")
        self.show_token_button.setObjectName("ghost")
        self.show_token_button.setCheckable(True)
        self.show_token_button.setFixedWidth(80)
        self.show_token_button.toggled.connect(self.toggle_token_visibility)
        token_row = QHBoxLayout()
        token_row.setSpacing(6)
        token_row.addWidget(self.token, 1)
        token_row.addWidget(self.show_token_button)

        self.verify_button = QPushButton("Verifica")
        self.verify_button.clicked.connect(self.verify_token)
        self.token_badge = QLabel()
        self.token_badge.setObjectName("badge")
        self.token_badge.setWordWrap(True)
        self.token_link = QLabel()
        self.token_link.setObjectName("hint")
        self.token_link.setOpenExternalLinks(True)
        self.token_link.setWordWrap(True)
        self.update_token_link()
        token_hint = QLabel("Il token resta in memoria solo finché l'app è aperta.")
        token_hint.setObjectName("hint")
        token_hint.setWordWrap(True)
        layout.addWidget(card(section_label("Autenticazione GitHub"), token_row, self.verify_button,
                              self.token_badge, self.token_link, token_hint))

        # Git: con git i commit si leggono da un clone locale, senza consumare quota API
        self.git_badge = QLabel()
        self.git_badge.setObjectName("badge")
        self.git_badge.setWordWrap(True)
        git_hint = QLabel("Con Git i commit si leggono da un clone locale temporaneo invece che dalle API: "
                          "indispensabile per i repository grandi.")
        git_hint.setObjectName("hint")
        git_hint.setWordWrap(True)
        self.git_link = QLabel()
        self.git_link.setObjectName("hint")
        self.git_link.setOpenExternalLinks(True)
        self.update_git_link()
        self.git_button = QPushButton("Ricontrolla")
        self.git_button.setObjectName("ghost")
        self.git_button.clicked.connect(self.check_git)
        git_row = QHBoxLayout()
        git_row.addWidget(self.git_link, 1)
        git_row.addWidget(self.git_button)
        layout.addWidget(card(section_label("Git · analisi dei commit"), self.git_badge, git_hint, git_row))

        # Tipo di grafo
        self.choice = QComboBox()
        for key, (title, _) in GRAPH_TYPES.items():
            self.choice.addItem(title, key)
        self.choice_description = QLabel()
        self.choice_description.setObjectName("hint")
        self.choice_description.setWordWrap(True)
        self.choice.currentIndexChanged.connect(self.update_choice_description)
        self.update_choice_description()
        layout.addWidget(card(section_label("Tipo di grafo"), self.choice, self.choice_description))

        # Intervallo temporale
        self.calendario_widget = CalendarioApp()
        layout.addWidget(card(section_label("Intervallo temporale"), self.calendario_widget))

        self.update_button = QPushButton("Genera grafo")
        self.update_button.setObjectName("primary")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(self.on_update_clicked)
        layout.addWidget(self.update_button)

        layout.addStretch(1)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("ghost")
        self.theme_button.clicked.connect(self.toggle_theme)
        self.update_theme_button()
        layout.addWidget(self.theme_button)
        return sidebar

    def build_content(self):
        content = QWidget()
        content.setObjectName("content")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        self.graph_title = QLabel("Nessun grafo")
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
        self.export_button = QPushButton("Esporta…")
        self.export_button.setObjectName("ghost")
        self.export_button.setToolTip("Esporta il grafo e i dati grezzi in CSV, GraphML e MATLAB (.mat)")
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
        return content

    def build_empty_state(self):
        empty = QWidget()
        layout = QVBoxLayout(empty)
        layout.addStretch(1)
        icon = QLabel("◎")
        icon.setObjectName("emptyIcon")
        title = QLabel("Nessun grafo da mostrare")
        title.setObjectName("emptyTitle")
        hint = QLabel("Inserisci owner e nome di un repository, scegli il tipo di grafo e l'intervallo,\n"
                      "poi premi «Genera grafo».")
        hint.setObjectName("subtitle")
        for w in (icon, title, hint):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(w)
        layout.addStretch(1)
        return empty

    # ---------- interazioni ----------

    def update_choice_description(self):
        self.choice_description.setText(GRAPH_TYPES[self.choice.currentData()][1])

    def toggle_token_visibility(self, visible: bool):
        self.token.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.show_token_button.setText("Nascondi" if visible else "Mostra")

    def update_token_link(self):
        color = palette(self.dark)["accent"]
        self.token_link.setText(f'<a style="color:{color}; text-decoration:none" href="{TOKEN_URL}">'
                                f'Come creare un token →</a> (fine-grained, sola lettura)')

    def on_token_changed(self):
        self.verified_token = None
        self.token_valid = None
        self.update_token_badge()

    def set_badge(self, text: str, state: str, badge: QLabel = None):
        badge = badge or self.token_badge
        badge.setText(text)
        badge.setProperty("state", state)
        badge.style().unpolish(badge)
        badge.style().polish(badge)

    def update_git_link(self):
        color = palette(self.dark)["accent"]
        self.git_link.setText(f'<a style="color:{color}; text-decoration:none" href="{GIT_URL}">Scarica Git →</a>')

    def check_git(self):
        GitHistory.refresh_path()  # git appena installato: non serve riavviare l'app
        self.git_version = GitHistory.git_version()
        if self.git_version is not None:
            self.set_badge(f"✓ Git {self.git_version} trovato · commit letti dal clone locale, "
                           "quasi nessuna richiesta API", "ok", self.git_badge)
            self.git_link.hide()
        else:
            self.set_badge("✕ Git non trovato · ogni commit costa 1 richiesta API", "error", self.git_badge)
            self.git_link.show()

    def update_token_badge(self, rate=None):
        if self.token.text().strip() == "":
            if rate is not None:
                self.set_badge(f"Nessun token · {quota_text(rate)}", "error" if rate["remaining"] == 0 else "neutral")
            else:
                self.set_badge("Nessun token · limite di 60 richieste/ora", "neutral")
        elif self.token_valid is None:
            self.set_badge("Token non ancora verificato", "neutral")
        elif self.token_valid:
            text = "✓ Autenticato"
            state = "ok"
            if rate is not None:
                text += f" · {quota_text(rate)}"
                if rate["remaining"] == 0:
                    state = "error"  # token valido ma quota esaurita fino al rinnovo
            self.set_badge(text, state)
        else:
            self.set_badge("✕ Token non valido o scaduto", "error")

    def verify_token(self):
        token = self.token.text()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            rate = APICalls.get_rate_limit(token)
        except requests.RequestException:
            self.set_badge("Impossibile contattare GitHub", "error")
            return False
        finally:
            QApplication.restoreOverrideCursor()
        self.verified_token = token
        self.token_valid = rate is not None
        self.update_token_badge(rate)
        return self.token_valid

    def validate_input(self):
        if self.owner.text().strip() == "" or self.repo_name.text().strip() == "":
            QMessageBox.warning(self, "Dati mancanti", "Inserisci owner e nome del repository.")
            return False

        if self.calendario_widget.date_edit_inizio.date() > self.calendario_widget.date_edit_fine.date():
            QMessageBox.warning(self, "Errore di selezione",
                                "La data di inizio deve essere precedente o uguale alla data di fine.")
            return False

        if not self.needs_download():
            return True  # i dati sono già in memoria: il token non serve

        if self.missing_parts()[0] and self.git_version is None:
            answer = QMessageBox.question(self, "Git non trovato",
                                          "Git non è installato (o non è nel PATH): i commit verranno scaricati "
                                          "via API, con 1 richiesta per ogni commit, e per i repository grandi "
                                          "la quota oraria può non bastare.\n\nPer usare il clone locale "
                                          "installa Git e premi «Ricontrolla».\n\nContinuare comunque?")
            if answer != QMessageBox.StandardButton.Yes:
                return False

        if self.token.text().strip() == "":
            answer = QMessageBox.question(self, "Nessun token",
                                          "Senza token il limite è di 60 richieste/ora, insufficiente per "
                                          "repository grandi.\n\nContinuare comunque?")
            return answer == QMessageBox.StandardButton.Yes

        # verifica automatica se il token non è stato ancora verificato (in caso di errore di rete si prosegue)
        if self.verified_token != self.token.text():
            self.verify_token()
        if self.token_valid is False:
            QMessageBox.critical(self, "Token non valido",
                                 "GitHub ha rifiutato il token inserito. Controlla che sia corretto e non scaduto.")
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
        need_files = choice in ("collaborazioni", "composito") and not self.covers(self.files_key, self.files_range)
        need_users = choice in ("comunicazioni", "composito") and not self.covers(self.users_key, self.users_range)
        return need_files, need_users

    def needs_download(self):
        return any(self.missing_parts())

    def on_update_clicked(self):
        if self.download_thread is not None:  # durante un download il pulsante lo annulla
            APICalls.cancel_event.set()
            self.update_button.setEnabled(False)
            self.update_button.setText("Annullamento in corso…")
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
        message = f"Recupero dei dati di {owner}/{repo} dal {start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}…"
        if (need_files and self.files_key == key) or (need_users and self.users_key == key):
            message = "L'intervallo scelto non è coperto dai dati in memoria: nuovo download. " + message
        self.statusBar().showMessage(message)
        self.download_thread.start()

    def set_busy(self, busy: bool):
        for w in (self.owner, self.repo_name, self.token, self.show_token_button, self.verify_button, self.choice,
                  self.calendario_widget, self.load_button, self.git_button):
            w.setEnabled(not busy)
        self.update_button.setEnabled(True)
        self.update_button.setText("Annulla download" if busy else "Genera grafo")
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
        resume = (dt.datetime.now() + dt.timedelta(seconds=seconds)).strftime('%H:%M')
        self.statusBar().showMessage(f"Limite API raggiunto: il download riprende alle {resume}")

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
        QMessageBox.critical(self, "Errore", f"Impossibile scaricare i dati:\n{error}")
        self.statusBar().showMessage("Errore durante il download dei dati")

    def on_download_cancelled(self):
        self.stop_download_thread()
        self.statusBar().showMessage("Download annullato: i dati già scaricati completamente restano in memoria")

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
        qinizio = self.calendario_widget.date_edit_inizio.date()
        qfine = self.calendario_widget.date_edit_fine.date()
        data_inizio, data_fine = self.selected_range()
        files = self.files if self.files_key == key else None
        users = self.users if self.users_key == key else None

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            edge_color = None
            if choice == "collaborazioni":
                g, _ = create_graph(owner, repo, data_inizio, "", data_inizio, data_fine, files)
                flag = 1
            elif choice == "comunicazioni":
                g, _ = create_graph_communication(owner, repo, data_inizio, "", data_inizio, data_fine, users)
                flag = 2
            else:
                g, _, _, edge_color = create_composite_graph(owner, repo, data_inizio, "", data_inizio,
                                                             data_fine, files, users)
                flag = 3
        except Exception as e:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Errore", f"Impossibile generare il grafo:\n{e}")
            self.statusBar().showMessage("Errore durante la generazione del grafo")
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.current_graph = (g, flag, edge_color, None)  # disposizione dei nodi calcolata al primo disegno
        self.show_graph()
        self.graph_title.setText(GRAPH_TYPES[choice][0])
        self.repo_chip.setText(f"{owner}/{repo}")
        self.nodes_chip.setText(f"{g.number_of_nodes()} sviluppatori")
        self.edges_chip.setText(f"{g.number_of_edges()} collegamenti")
        for chip in (self.repo_chip, self.nodes_chip, self.edges_chip):
            chip.show()
        # contesto del grafo mostrato: l'esportazione resta coerente anche se poi si cambia il calendario
        self.graph_context = {"owner": owner, "repo": repo, "kind": choice, "start": data_inizio,
                              "end": data_fine, "files": files, "users": users}
        self.export_button.show()
        self.show_rate_limit_status(qinizio, qfine)

    def export_graph(self):
        if self.graph_context is None:
            return
        result = run_export_dialog(self.graph_context, self)
        if result:
            created, count = result
            folder = os.path.dirname(created[0])
            if created[0].endswith(".zip"):
                self.statusBar().showMessage(f"Esportato {os.path.basename(created[0])} ({count} file) in {folder}")
            else:
                self.statusBar().showMessage(f"{count} file esportat{'o' if count == 1 else 'i'} in {folder}")

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

    def show_rate_limit_status(self, qinizio, qfine):
        message = f"Intervallo: {qinizio.toString('dd/MM/yyyy')} – {qfine.toString('dd/MM/yyyy')}"
        rate = APICalls.last_rate_limit
        if "remaining" in rate and "limit" in rate:
            message += f"   ·   Quota API: {quota_text(rate)}"
            if self.token_valid or self.token.text().strip() == "":
                self.update_token_badge(dict(rate))
        else:
            message += "   ·   Dati già in memoria"
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
        hint = f"Dati disponibili dal {start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}"
        if activity is not None:
            hint += (f" · attività registrata dal {activity[0].strftime('%d/%m/%Y')} "
                     f"al {activity[1].strftime('%d/%m/%Y')}")
        self.calendario_widget.set_hint(hint)

    def update_data_status(self):
        self.apply_data_range()
        key = self.current_key()
        has_files = self.files is not None and self.files_key == key
        has_users = self.users is not None and self.users_key == key
        self.save_button.setEnabled((has_files or has_users) and self.download_thread is None)
        if not (has_files or has_users):
            self.data_status.setText("Nessun dato in memoria per questo repository: genera un grafo per "
                                     "scaricarli da GitHub, oppure carica un file salvato in precedenza.")
            return
        def part(name, present, data_range):
            if not present:
                return f"{name} ✕"
            if data_range is None:
                return f"{name} ✓"
            return f"{name} ✓ {data_range[0].strftime('%d/%m/%Y')}–{data_range[1].strftime('%d/%m/%Y')}"

        text = (f"{key[0]}/{key[1]} · {part('collaborazioni', has_files, self.files_range)} · "
                f"{part('comunicazioni', has_users, self.users_range)}")
        if self.data_date is not None:
            text += f" · dati del {self.data_date.strftime('%d/%m/%Y %H:%M')}"
        self.data_status.setText(text)

    def save_data_file(self):
        owner, repo = self.current_key()
        files = self.files if self.files_key == (owner, repo) else None
        users = self.users if self.users_key == (owner, repo) else None
        files_range = self.files_range if files is not None else None
        users_range = self.users_range if users is not None else None
        default = os.path.join(os.path.expanduser("~"), f"{owner}_{repo}{DATA_EXTENSION}")
        path, _ = QFileDialog.getSaveFileName(self, "Salva dati del repository", default, DATA_FILTER)
        if not path:
            return
        if not path.endswith(DATA_EXTENSION):
            path += DATA_EXTENSION
        try:
            starts = [r[0] for r in (files_range, users_range) if r is not None]
            save_data(path, owner, repo, min(starts) if starts else self.selected_range()[0], files, users,
                      files_range, users_range)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare i dati:\n{e}")
            return
        self.statusBar().showMessage(f"Dati di {owner}/{repo} salvati in {path}")

    def load_data_file(self):
        start_dir = EXAMPLES_DIR if os.path.isdir(EXAMPLES_DIR) else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Carica dati del repository", start_dir, DATA_FILTER)
        if not path:
            return
        try:
            data = load_data(path)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Errore", f"Impossibile caricare i dati:\n{e}")
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
        message = f"Dati di {key[0]}/{key[1]} caricati da {os.path.basename(path)}"
        if self.data_range is not None:
            message += f": disponibili dal {start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}"
        self.statusBar().showMessage(message)

        # se il file contiene i dati per il tipo di grafo scelto, lo genera subito
        if not self.needs_download():
            self.update_graph()

    def update_theme_button(self):
        self.theme_button.setText("☀  Tema chiaro" if self.dark else "☾  Tema scuro")

    def toggle_theme(self):
        self.dark = not self.dark
        apply_theme(QApplication.instance(), self.dark)
        self.update_theme_button()
        self.update_token_link()
        self.update_git_link()
        self.show_graph()


def main():
    app = QApplication(sys.argv)
    apply_theme(app, True)
    viewer = MainViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
