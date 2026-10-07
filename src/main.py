import sys
import datetime as dt

import requests
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication,
                             QLineEdit, QFormLayout, QComboBox, QFrame, QLabel, QScrollArea)

from src.gui.graph import create_graph, GraphWidget, create_graph_communication, create_composite_graph
from src.gui.style import apply_theme, palette
from src.gui.widget_calendar import CalendarioApp
from src.logic import APICalls

TOKEN_URL = "https://github.com/settings/personal-access-tokens/new"

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


def format_number(n: int):
    return f"{n:,}".replace(",", ".")


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

        # dati già scaricati, con la coppia (owner, repo) a cui si riferiscono
        self.files = None
        self.files_key = None
        self.users = None
        self.users_key = None

        # esito dell'ultima verifica del token (il token resta solo in memoria)
        self.verified_token = None
        self.token_valid = None

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
        self.datainizio = dt.datetime(2023, 11, 15)
        self.calendario_widget = CalendarioApp(self.datainizio)
        layout.addWidget(card(section_label("Intervallo temporale"), self.calendario_widget))

        self.update_button = QPushButton("Genera grafo")
        self.update_button.setObjectName("primary")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(self.update_graph)
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

    def set_badge(self, text: str, state: str):
        self.token_badge.setText(text)
        self.token_badge.setProperty("state", state)
        self.token_badge.style().unpolish(self.token_badge)
        self.token_badge.style().polish(self.token_badge)

    def update_token_badge(self, rate=None):
        if self.token.text().strip() == "":
            self.set_badge("Nessun token · limite di 60 richieste/ora", "neutral")
        elif self.token_valid is None:
            self.set_badge("Token non ancora verificato", "neutral")
        elif self.token_valid:
            text = "✓ Autenticato"
            if rate is not None:
                text += f" · {format_number(rate['remaining'])}/{format_number(rate['limit'])} richieste"
            self.set_badge(text, "ok")
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

        if self.token.text().strip() == "":
            answer = QMessageBox.question(self, "Nessun token",
                                          "Senza token il limite è di 60 richieste/ora, insufficiente per "
                                          "repository grandi (se non sono già in cache).\n\nContinuare comunque?")
            return answer == QMessageBox.StandardButton.Yes

        # verifica automatica se il token non è stato ancora verificato (in caso di errore di rete si prosegue)
        if self.verified_token != self.token.text():
            self.verify_token()
        if self.token_valid is False:
            QMessageBox.critical(self, "Token non valido",
                                 "GitHub ha rifiutato il token inserito. Controlla che sia corretto e non scaduto.")
            return False
        return True

    def update_graph(self):
        if not self.validate_input():
            return

        owner = self.owner.text().strip()
        repo = self.repo_name.text().strip()
        key = (owner, repo)
        token = self.token.text().strip()
        choice = self.choice.currentData()
        qinizio = self.calendario_widget.date_edit_inizio.date()
        qfine = self.calendario_widget.date_edit_fine.date()
        data_inizio = dt.datetime(qinizio.year(), qinizio.month(), qinizio.day())
        data_fine = dt.datetime(qfine.year(), qfine.month(), qfine.day(), 23, 59, 59)

        files = self.files if self.files_key == key else None
        users = self.users if self.users_key == key else None

        self.update_button.setEnabled(False)
        self.update_button.setText("Generazione in corso…")
        self.statusBar().showMessage(f"Recupero dei dati di {owner}/{repo}…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        APICalls.last_rate_limit.clear()
        try:
            edge_color = None
            if choice == "collaborazioni":
                g, self.files = create_graph(owner, repo, self.datainizio, token, data_inizio, data_fine, files)
                self.files_key = key
                flag = 1
            elif choice == "comunicazioni":
                g, self.users = create_graph_communication(owner, repo, self.datainizio, token, data_inizio,
                                                           data_fine, users)
                self.users_key = key
                flag = 2
            else:
                g, self.files, self.users, edge_color = create_composite_graph(owner, repo, self.datainizio, token,
                                                                               data_inizio, data_fine, files, users)
                self.files_key = self.users_key = key
                flag = 3
        except Exception as e:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Errore", f"Impossibile generare il grafo:\n{e}")
            self.statusBar().showMessage("Errore durante la generazione del grafo")
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.update_button.setEnabled(True)
            self.update_button.setText("Genera grafo")

        self.current_graph = (g, flag, edge_color)
        self.show_graph()
        self.graph_title.setText(GRAPH_TYPES[choice][0])
        self.repo_chip.setText(f"{owner}/{repo}")
        self.nodes_chip.setText(f"{g.number_of_nodes()} sviluppatori")
        self.edges_chip.setText(f"{g.number_of_edges()} collegamenti")
        for chip in (self.repo_chip, self.nodes_chip, self.edges_chip):
            chip.show()
        self.show_rate_limit_status(qinizio, qfine)

    def show_graph(self):
        if self.current_graph is None:
            return
        if self.graph_widget is not None:
            self.graph_layout.removeWidget(self.graph_widget)
            self.graph_widget.deleteLater()
        self.empty_state.hide()
        g, flag, edge_color = self.current_graph
        self.graph_widget = GraphWidget(g, flag, edge_color, self.dark)
        self.graph_layout.addWidget(self.graph_widget)

    def show_rate_limit_status(self, qinizio, qfine):
        message = f"Intervallo: {qinizio.toString('dd/MM/yyyy')} – {qfine.toString('dd/MM/yyyy')}"
        rate = APICalls.last_rate_limit
        if "remaining" in rate and "limit" in rate:
            message += (f"   ·   Richieste API rimanenti: {format_number(rate['remaining'])}/"
                        f"{format_number(rate['limit'])}")
            if "reset" in rate:
                message += f" · reset alle {dt.datetime.fromtimestamp(rate['reset']).strftime('%H:%M')}"
            if self.token_valid:
                self.update_token_badge(rate)
        else:
            message += "   ·   Dati letti dalla cache locale"
        self.statusBar().showMessage(message)

    def update_theme_button(self):
        self.theme_button.setText("☀  Tema chiaro" if self.dark else "☾  Tema scuro")

    def toggle_theme(self):
        self.dark = not self.dark
        apply_theme(QApplication.instance(), self.dark)
        self.update_theme_button()
        self.update_token_link()
        self.show_graph()


def main():
    app = QApplication(sys.argv)
    apply_theme(app, True)
    viewer = MainViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
