import os
import re
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton,
                             QFileDialog, QDialogButtonBox, QMessageBox)

from src.logic import Export

# modalità di esportazione: chiave -> (etichetta, descrizione); i file prodotti sono in Export.EXPORT_SUFFIXES
EXPORTS = {
    "csv": ("Nodi e archi (CSV)", "R: igraph::graph_from_data_frame, tidygraph · MATLAB: readtable → digraph"),
    "graphml": ("GraphML", "R: igraph::read_graph(…, \"graphml\") · Python: NetworkX · Gephi, Cytoscape"),
    "mat": ("MATLAB (.mat)", "load(…) e poi digraph(A, names) o graph(A, names)"),
    "edits": ("Modifiche ai file con data (CSV)", "sviluppatore–file–data: reti bipartite e analisi nel tempo"),
    "interactions": ("Interazioni con data (CSV)",
                     "mittente–destinatario–data: reti temporali (networkDynamic/tsna, pathpy)"),
}


def default_prefix(context: Dict) -> str:
    name = f"{context['owner']}_{context['repo']}_{context['kind']}_" \
           f"{context['start'].strftime('%Y%m%d')}-{context['end'].strftime('%Y%m%d')}"
    return re.sub(r"[^\w.\-]", "_", name)


def available_exports(context: Dict) -> List[str]:
    # i dati grezzi si esportano solo se pertinenti al tipo di grafo e presenti in memoria
    keys = ["csv", "graphml", "mat"]
    if context["kind"] in ("collaborazioni", "composito") and context["files"] is not None:
        keys.append("edits")
    if context["kind"] in ("comunicazioni", "composito") and context["users"] is not None:
        keys.append("interactions")
    return keys


class ExportDialog(QDialog):
    def __init__(self, context: Dict, parent=None):
        super().__init__(parent)
        self.context = context
        self.created: List[str] = []
        self.file_count = 0  # file esportati (contenuti nello zip, se più modalità)
        self.setWindowTitle("Esporta per l'analisi")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        summary = QLabel(f"<b>{context['owner']}/{context['repo']}</b> · grafo {context['kind']} · dal "
                         f"{context['start'].strftime('%d/%m/%Y')} al {context['end'].strftime('%d/%m/%Y')}")
        layout.addWidget(summary)

        available = available_exports(context)
        self.checks: Dict[str, QCheckBox] = {}
        for key, (label, description) in EXPORTS.items():
            check = QCheckBox(label)
            check.setChecked(key in available)
            check.setEnabled(key in available)
            check.toggled.connect(self.update_preview)
            hint = QLabel(description if key in available else "non disponibile per questo grafo")
            hint.setObjectName("hint")
            row = QVBoxLayout()
            row.setSpacing(0)
            row.addWidget(check)
            row.addWidget(hint)
            layout.addLayout(row)
            self.checks[key] = check

        self.directory = QLineEdit(os.path.expanduser("~"))
        browse = QPushButton("Sfoglia…")
        browse.clicked.connect(self.choose_directory)
        directory_row = QHBoxLayout()
        directory_row.addWidget(QLabel("Cartella"))
        directory_row.addWidget(self.directory, 1)
        directory_row.addWidget(browse)
        layout.addLayout(directory_row)

        self.prefix = QLineEdit(default_prefix(context))
        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel("Nome dei file"))
        prefix_row.addWidget(self.prefix, 1)
        layout.addLayout(prefix_row)
        self.prefix.textChanged.connect(self.update_preview)
        self.directory.textChanged.connect(self.update_preview)

        self.preview = QLabel()
        self.preview.setObjectName("hint")
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.export_button = self.buttons.addButton("Esporta", QDialogButtonBox.ButtonRole.AcceptRole)
        self.export_button.setObjectName("primary")
        self.buttons.accepted.connect(self.export)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.update_preview()

    def selected_keys(self) -> List[str]:
        return [key for key, check in self.checks.items() if check.isChecked() and check.isEnabled()]

    def update_preview(self):
        keys, prefix = self.selected_keys(), self.prefix.text().strip()
        self.export_button.setEnabled(bool(keys) and prefix != "")
        if not keys:
            self.preview.setText("Seleziona almeno un file da esportare.")
        elif len(keys) > 1:  # più modalità: un unico archivio
            self.preview.setText(f"File: {prefix}.zip — contiene: " + ", ".join(Export.file_names(keys, prefix)))
        else:
            self.preview.setText("File: " + ", ".join(Export.file_names(keys, prefix)))

    def choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Cartella di destinazione", self.directory.text())
        if directory:
            self.directory.setText(directory)

    def export(self):
        directory = self.directory.text().strip()
        if not os.path.isdir(directory):
            QMessageBox.warning(self, "Cartella non valida", "La cartella di destinazione non esiste.")
            return
        keys, prefix = self.selected_keys(), self.prefix.text().strip()
        existing = [n for n in Export.output_names(keys, prefix) if os.path.exists(os.path.join(directory, n))]
        if existing:
            answer = QMessageBox.question(self, "File già presenti",
                                          "Questi file esistono già e verranno sovrascritti:\n" + "\n".join(existing)
                                          + "\n\nContinuare?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self.created = Export.export_files(self.context, keys, directory, prefix)
            self.file_count = len(Export.file_names(keys, prefix))
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Errore", f"Impossibile esportare:\n{e}")
            return
        self.accept()


# ritorna (percorsi creati, numero di file esportati) oppure None se annullato
def run_export_dialog(context: Dict, parent=None) -> Optional[Tuple[List[str], int]]:
    dialog = ExportDialog(context, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.created, dialog.file_count
    return None
