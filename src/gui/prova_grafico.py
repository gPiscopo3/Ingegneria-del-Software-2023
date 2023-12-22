import sys

from PyQt6.QtWidgets import (QWidget, QMainWindow, QVBoxLayout, QPushButton, QGraphicsScene, QGraphicsView, \
                             QMessageBox, QApplication, QLineEdit, QFormLayout, QComboBox)

from widget_calendar import CalendarioApp

import datetime as dt
from src.gui.graph import create_graph, GraphWidget, create_graph_communication, create_composite_graph

TOKEN = "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"


def init_graph():
    print("Inizialied")


class MainViewer(QMainWindow):
    previous_owner = ""
    previous_repo = ""
    previous_choice = ""
    files = dict()
    users = dict()
    edge_color = []

    def __init__(self):
        super().__init__()

        self.text_choice = None
        self.graph_widget = None
        self.setWindowTitle('App di Giovanni')
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        # Input Box - Owner, Repository Name, Token
        self.owner = QLineEdit()
        self.repo_name = QLineEdit()
        self.token = QLineEdit()
        self.choice = QComboBox()

        form = QFormLayout()
        form.addRow("Repository owner", self.owner)
        form.addRow("Repository name", self.repo_name)
        form.addRow("Github token", self.token)
        form.addRow("Tipo Grafo", self.choice)
        self.layout.addLayout(form)

        self.choice.addItem("collaborazioni")
        self.choice.addItem("comunicazioni")
        self.choice.addItem("composito")
        self.layout.addWidget(self.choice)

        # Calendario per selezionare l'intervallo temporale
        self.datainizio = dt.datetime(2023, 11, 15)
        self.calendario_widget = CalendarioApp(self.datainizio)
        self.layout.addWidget(self.calendario_widget)

        # Pulsante per aggiornare il grafico in base all'intervallo selezionato
        self.update_button = QPushButton('Aggiorna Grafico', self)
        self.update_button.clicked.connect(self.update_graph)
        self.layout.addWidget(self.update_button)

        # Scena e vista per visualizzare il grafico
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.layout.addWidget(self.view)

        # Chiamata a una funzione di esempio per inizializzare il grafico
        init_graph()

    def update_graph(self):
        if self.graph_widget is not None:
            self.layout.removeWidget(self.graph_widget)
        datainizio = self.datainizio
        data_inizio = self.calendario_widget.date_edit_inizio.date()
        data_fine = self.calendario_widget.date_edit_fine.date()
        self.text_choice = self.choice.currentText()

        if data_inizio <= data_fine:
            QMessageBox.information(self, 'Selezione Confermata',
                                    f'Intervallo selezionato:\nInizio: {data_inizio.toString("yyyy-MM-dd")}\nFine: {data_fine.toString("yyyy-MM-dd")}')
        else:
            QMessageBox.warning(self, 'Errore di Selezione',
                                'La data di inizio deve essere inferiore o uguale alla data di fine.')

        if (self.owner.text().__eq__(self.previous_owner) and self.repo_name.text().__eq__(self.previous_repo)
                and self.text_choice.__eq__(self.previous_choice)):
            if self.text_choice == "collaborazioni":
                g, self.files = create_graph(self.owner.text(), self.repo_name.text(), datainizio, TOKEN, data_inizio,
                                             data_fine,
                                             self.files)
                self.graph_widget = GraphWidget(g, 1, None)

            elif self.text_choice == "comunicazioni":
                g, self.users = create_graph_communication(self.owner.text(), self.repo_name.text(), datainizio, TOKEN,
                                                           data_inizio, data_fine, self.users)
                self.graph_widget = GraphWidget(g, 2, None)

            elif self.text_choice == "composito":
                g, self.files, self.users, self.edge_color = create_composite_graph(self.owner.text(),
                                                                                    self.repo_name.text(), datainizio,
                                                                                    TOKEN,
                                                                                    data_inizio, data_fine, self.files,
                                                                                    self.users)
                self.graph_widget = GraphWidget(g, 3, self.edge_color)

        else:
            if self.text_choice == "collaborazioni":
                g, self.files = create_graph(self.owner.text(), self.repo_name.text(), datainizio, TOKEN, data_inizio,
                                             data_fine, None)
                self.graph_widget = GraphWidget(g, 1, None)

            elif self.text_choice == "comunicazioni":
                g, self.users = create_graph_communication(self.owner.text(), self.repo_name.text(), datainizio, TOKEN,
                                                           data_inizio, data_fine, None)
                self.graph_widget = GraphWidget(g, 2, None)

            elif self.text_choice == "composito":
                g, self.files, self.users, self.edge_color = create_composite_graph(self.owner.text(),
                                                                                    self.repo_name.text(), datainizio,
                                                                                    TOKEN,
                                                                                    data_inizio, data_fine, None,
                                                                                    None)
                self.graph_widget = GraphWidget(g, 3, self.edge_color)
        self.scene.addWidget(self.graph_widget)
        self.graph_widget.setFixedSize(1550, 580)

        init_graph()  # Aggiorna il grafico con i nuovi dati
        self.previous_owner = self.owner.text()
        self.previous_repo = self.repo_name.text()
        self.previous_choice = self.choice.currentText()


def main():
    app = QApplication(sys.argv)
    viewer = MainViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
