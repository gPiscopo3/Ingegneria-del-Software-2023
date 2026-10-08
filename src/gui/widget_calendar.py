from datetime import date

from PyQt6.QtWidgets import QWidget, QFormLayout, QDateEdit, QLabel
from PyQt6.QtCore import QDate

MIN_DATE = date(2008, 1, 1)  # nessun dato su GitHub prima della sua nascita
DEFAULT_MONTHS = 3  # intervallo proposto: ultimi 3 mesi


class CalendarioApp(QWidget):
    def __init__(self):
        super().__init__()
        self.date_edit_fine = None
        self.date_edit_inizio = None
        self.hint = None
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

    # limita la scelta al periodo [start, end] e seleziona [select_start, end] (di default tutto il periodo)
    def set_range(self, start, end, select_start=None):
        start, end = QDate(start.year, start.month, start.day), QDate(end.year, end.month, end.day)
        for date_edit in (self.date_edit_inizio, self.date_edit_fine):
            date_edit.setDateRange(start, end)
        self.date_edit_inizio.setDate(QDate(select_start.year, select_start.month, select_start.day)
                                      if select_start else start)
        self.date_edit_fine.setDate(end)

    # limiti di default: qualsiasi data fino a oggi, con selezionati gli ultimi mesi
    def reset_range(self):
        today = QDate.currentDate()
        self.set_range(MIN_DATE, today.toPyDate(), today.addMonths(-DEFAULT_MONTHS).toPyDate())
        self.set_hint("")

    def set_hint(self, text: str):
        self.hint.setText(text)
        self.hint.setVisible(text != "")
