import sys

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QWidget, QMainWindow, QVBoxLayout, QPushButton, QGraphicsScene, QGraphicsView, \
                             QMessageBox, QApplication, QLineEdit, QFormLayout)

from widget_calendar import CalendarioApp  # Assicurati che il nome del file sia corretto

import datetime as dt

from src.gui.graph import GraphWidget, create_graph

TOKEN = ""


def init_graph():
    print("Inizialied")


class GraphViewer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.graph_widget = None
        self.setWindowTitle('Grafo delle collaborazioni')
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        # Input Box - Owner, Repository Name, Token
        self.owner = QLineEdit()
        self.repo_name = QLineEdit()
        self.token = QLineEdit()

        form = QFormLayout()
        form.addRow("Repository owner", self.owner)
        form.addRow("Repository name", self.repo_name)
        form.addRow("Github token", self.token)
        self.layout.addLayout(form)

        # Calendario per selezionare l'intervallo temporale
        self.calendario_widget = CalendarioApp()
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
        datainizio = dt.datetime(2023, 11, 28)
        data_inizio = self.calendario_widget.date_edit_inizio.date()
        data_fine = self.calendario_widget.date_edit_fine.date()

        g = create_graph(self.owner.text(), self.repo_name.text(), datainizio, TOKEN, data_inizio, data_fine)
        self.graph_widget = GraphWidget(g)
        self.layout.addWidget(self.graph_widget)
        # Funzione chiamata quando l'utente preme il pulsante "Aggiorna Grafico"
        # Qui dovresti aggiornare il grafico in base all'intervallo temporale selezionato

        print()

        if data_inizio <= data_fine:
            QMessageBox.information(self, 'Selezione Confermata',
                                    f'Intervallo selezionato:\nInizio: {data_inizio.toString("yyyy-MM-dd")}\nFine: {data_fine.toString("yyyy-MM-dd")}')
        else:
            QMessageBox.warning(self, 'Errore di Selezione',
                                'La data di inizio deve essere inferiore o uguale alla data di fine.')

        # Qui dovresti aggiornare il tuo grafico in base alle date selezionate
        # Ad esempio, puoi rimuovere gli elementi precedenti dalla scena e aggiungere quelli nuovi.
        self.scene.clear()  # Rimuove gli elementi precedenti dalla scena
        init_graph()  # Aggiorna il grafico con i nuovi dati


def main():
    app = QApplication(sys.argv)
    viewer = GraphViewer()
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
