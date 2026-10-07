from PyQt6.QtWidgets import QWidget, QFormLayout, QDateEdit, QLabel
from PyQt6.QtCore import QDate


class CalendarioApp(QWidget):
    def __init__(self, datainizio):
        super().__init__()
        self.date_edit_fine = None
        self.date_edit_inizio = None
        self.hint = None
        self.datainizio = datainizio
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Seleziona Intervallo Temporale')

        # FormLayout per le date di inizio e fine
        form_layout = QFormLayout(self)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setVerticalSpacing(8)

        # QDateEdit per la data di inizio
        self.date_edit_inizio = self.create_date_edit()
        form_layout.addRow('Dal', self.date_edit_inizio)

        # QDateEdit per la data di fine, di default oggi
        self.date_edit_fine = self.create_date_edit()
        form_layout.addRow('Al', self.date_edit_fine)

        # periodo disponibile nei dati caricati da file (nascosto se vuoto)
        self.hint = QLabel()
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        form_layout.addRow(self.hint)

        self.reset_range()

    def create_date_edit(self):
        date_edit = QDateEdit(self)
        date_edit.setDisplayFormat('dd/MM/yyyy')
        date_edit.setCalendarPopup(True)
        return date_edit

    # limita la scelta al periodo [start, end] e lo seleziona per intero
    def set_range(self, start, end):
        start, end = QDate(start.year, start.month, start.day), QDate(end.year, end.month, end.day)
        for date_edit in (self.date_edit_inizio, self.date_edit_fine):
            date_edit.setDateRange(start, end)
        self.date_edit_inizio.setDate(start)
        self.date_edit_fine.setDate(end)

    # limiti di default: dalla data minima dei download a oggi
    def reset_range(self):
        self.set_range(self.datainizio, QDate.currentDate().toPyDate())
        self.set_hint("")

    def set_hint(self, text: str):
        self.hint.setText(text)
        self.hint.setVisible(text != "")
