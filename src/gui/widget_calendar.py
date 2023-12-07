import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, \
    QDateEdit, QFormLayout, QCalendarWidget, QSizePolicy, QMessageBox, QGraphicsScene, QGraphicsView
from PyQt6.QtCore import QDate, Qt
import datetime as dt


class CalendarioApp(QWidget):
    def __init__(self, datainizio):
        super().__init__()
        self.date_edit_fine = None
        self.date_edit_inizio = None
        self.datainizio = datainizio
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Seleziona Intervallo Temporale')

        # Layout principale
        layout = QVBoxLayout()

        # FormLayout per le date di inizio e fine
        form_layout = QFormLayout()

        # QDateEdit per la data di inizio
        self.date_edit_inizio = QDateEdit(self)
        self.date_edit_inizio.setDisplayFormat('yyyy-MM-dd')
        self.date_edit_inizio.setCalendarPopup(True)
        self.date_edit_inizio.setMinimumDate(self.datainizio)
        self.date_edit_inizio.setMaximumDate(QDate.currentDate())
        form_layout.addRow('Inizio:', self.date_edit_inizio)

        # QDateEdit per la data di fine
        self.date_edit_fine = QDateEdit(self)
        self.date_edit_fine.setDisplayFormat('yyyy-MM-dd')
        self.date_edit_fine.setCalendarPopup(True)
        self.date_edit_fine.setMinimumDate(self.datainizio)
        self.date_edit_fine.setMaximumDate(QDate.currentDate())
        form_layout.addRow('Fine:', self.date_edit_fine)

        layout.addLayout(form_layout)
        self.setLayout(layout)
