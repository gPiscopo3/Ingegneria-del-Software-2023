import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, \
    QDateEdit, QFormLayout, QCalendarWidget, QSizePolicy, QMessageBox, QGraphicsScene, QGraphicsView
from PyQt6.QtCore import QDate, Qt


class CalendarioApp(QWidget):
    def __init__(self):
        super().__init__()

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
        self.date_edit_inizio.setDate(QDate.currentDate())  # Imposta la data odierna
        form_layout.addRow('Inizio:', self.date_edit_inizio)

        # QDateEdit per la data di fine
        self.date_edit_fine = QDateEdit(self)
        self.date_edit_fine.setDisplayFormat('yyyy-MM-dd')
        self.date_edit_fine.setCalendarPopup(True)
        self.date_edit_fine.setDate(QDate.currentDate())  # Imposta la data odierna
        form_layout.addRow('Fine:', self.date_edit_fine)

        layout.addLayout(form_layout)
        self.setLayout(layout)



