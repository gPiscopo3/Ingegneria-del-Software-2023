from PyQt6.QtWidgets import QWidget, QFormLayout, QDateEdit
from PyQt6.QtCore import QDate


class CalendarioApp(QWidget):
    def __init__(self, datainizio):
        super().__init__()
        self.date_edit_fine = None
        self.date_edit_inizio = None
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
        self.date_edit_inizio.setDate(self.date_edit_inizio.minimumDate())
        form_layout.addRow('Dal', self.date_edit_inizio)

        # QDateEdit per la data di fine, di default oggi
        self.date_edit_fine = self.create_date_edit()
        self.date_edit_fine.setDate(QDate.currentDate())
        form_layout.addRow('Al', self.date_edit_fine)

    def create_date_edit(self):
        date_edit = QDateEdit(self)
        date_edit.setDisplayFormat('dd/MM/yyyy')
        date_edit.setCalendarPopup(True)
        date_edit.setMinimumDate(self.datainizio)
        date_edit.setMaximumDate(QDate.currentDate())
        return date_edit
