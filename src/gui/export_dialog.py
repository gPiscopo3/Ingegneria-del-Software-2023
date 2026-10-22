import os
import re
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QPushButton,
                             QFileDialog, QDialogButtonBox, QMessageBox, QComboBox)

from src import i18n
from src.i18n import tr
from src.logic import Export

# modalità di esportazione: chiave -> chiavi di traduzione di etichetta e descrizione;
# i file prodotti sono in Export.EXPORT_SUFFIXES
EXPORTS = {
    "csv": ("export.csv.label", "export.csv.description"),
    "graphml": ("export.graphml.label", "export.graphml.description"),
    "mat": ("export.mat.label", "export.mat.description"),
    "edits": ("export.edits.label", "export.edits.description"),
    "interactions": ("export.interactions.label", "export.interactions.description"),
    "image": ("export.image.label", "export.image.description"),
}
IMAGE_FORMATS = {"png": "export.format.png", "svg": "export.format.svg", "pdf": "export.format.pdf"}
GRAPH_TITLES = {"collaboration": "graph.collaboration.title", "communication": "graph.communication.title",
                "composite": "graph.composite.title"}


def default_prefix(context: Dict) -> str:
    name = f"{context['owner']}_{context['repo']}_{context['kind']}_" \
           f"{context['start'].strftime('%Y%m%d')}-{context['end'].strftime('%Y%m%d')}"
    return re.sub(r"[^\w.\-]", "_", name)


def available_exports(context: Dict) -> List[str]:
    # i dati grezzi si esportano solo se pertinenti al tipo di grafo e presenti in memoria
    keys = ["csv", "graphml", "mat"]
    if context["kind"] in ("collaboration", "composite") and context["files"] is not None:
        keys.append("edits")
    if context["kind"] in ("communication", "composite") and context["users"] is not None:
        keys.append("interactions")
    if context.get("draw_image") is not None:
        keys.append("image")
    return keys


class ExportDialog(QDialog):
    def __init__(self, context: Dict, parent=None):
        super().__init__(parent)
        self.context = context
        self.created: List[str] = []
        self.file_count = 0  # file esportati (contenuti nello zip, se più modalità)
        self.setWindowTitle(tr("export.title"))
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        summary = QLabel(f"<b>{context['owner']}/{context['repo']}</b> · " +
                         tr("export.summary", graph=tr(GRAPH_TITLES[context["kind"]]),
                            start=i18n.format_date(context["start"]), end=i18n.format_date(context["end"])))
        layout.addWidget(summary)

        available = available_exports(context)
        self.checks: Dict[str, QCheckBox] = {}
        for key, (label, description) in EXPORTS.items():
            check = QCheckBox(tr(label))
            check.setChecked(key in available and key != "image")  # l'immagine si sceglie esplicitamente
            check.setEnabled(key in available)
            check.toggled.connect(self.update_preview)
            hint = QLabel(tr(description) if key in available else tr("export.unavailable"))
            hint.setObjectName("hint")
            row = QVBoxLayout()
            row.setSpacing(0)
            row.addWidget(check)
            row.addWidget(hint)
            layout.addLayout(row)
            self.checks[key] = check

        # opzioni dell'immagine: formato e sfondo
        self.image_format = QComboBox()
        for image_format, label in IMAGE_FORMATS.items():
            self.image_format.addItem(tr(label), image_format)
        self.light_background = QCheckBox(tr("export.light_background"))
        self.light_background.setChecked(True)
        image_row = QHBoxLayout()
        image_row.setContentsMargins(24, 0, 0, 0)
        image_row.addWidget(QLabel(tr("export.format")))
        image_row.addWidget(self.image_format)
        image_row.addSpacing(12)
        image_row.addWidget(self.light_background)
        image_row.addStretch(1)
        layout.addLayout(image_row)
        self.image_format.currentIndexChanged.connect(self.update_preview)
        self.checks["image"].toggled.connect(self.update_image_options)

        self.directory = QLineEdit(os.path.expanduser("~"))
        browse = QPushButton(tr("export.browse"))
        browse.clicked.connect(self.choose_directory)
        directory_row = QHBoxLayout()
        directory_row.addWidget(QLabel(tr("export.folder")))
        directory_row.addWidget(self.directory, 1)
        directory_row.addWidget(browse)
        layout.addLayout(directory_row)

        self.prefix = QLineEdit(default_prefix(context))
        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel(tr("export.file_name")))
        prefix_row.addWidget(self.prefix, 1)
        layout.addLayout(prefix_row)
        self.prefix.textChanged.connect(self.update_preview)
        self.directory.textChanged.connect(self.update_preview)

        self.preview = QLabel()
        self.preview.setObjectName("hint")
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.export_button = self.buttons.addButton(tr("export.confirm"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.export_button.setObjectName("primary")
        self.buttons.accepted.connect(self.export)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.update_image_options()

    def update_image_options(self):
        enabled = self.checks["image"].isChecked() and self.checks["image"].isEnabled()
        self.image_format.setEnabled(enabled)
        self.light_background.setEnabled(enabled)
        self.update_preview()

    def selected_format(self) -> str:
        return self.image_format.currentData()

    def selected_keys(self) -> List[str]:
        return [key for key, check in self.checks.items() if check.isChecked() and check.isEnabled()]

    def update_preview(self):
        keys, prefix = self.selected_keys(), self.prefix.text().strip()
        self.export_button.setEnabled(bool(keys) and prefix != "")
        if not keys:
            self.preview.setText(tr("export.select_one"))
        elif len(keys) > 1:  # più modalità: un unico archivio
            self.preview.setText(tr("export.preview_zip", name=f"{prefix}.zip",
                                    files=", ".join(Export.file_names(keys, prefix, self.selected_format()))))
        else:
            self.preview.setText(tr("export.preview_files",
                                    files=", ".join(Export.file_names(keys, prefix, self.selected_format()))))

    def choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, tr("export.choose_folder"), self.directory.text())
        if directory:
            self.directory.setText(directory)

    def export(self):
        directory = self.directory.text().strip()
        if not os.path.isdir(directory):
            QMessageBox.warning(self, tr("export.invalid_folder.title"), tr("export.invalid_folder.text"))
            return
        keys, prefix = self.selected_keys(), self.prefix.text().strip()
        image_format = self.selected_format()
        existing = [n for n in Export.output_names(keys, prefix, image_format)
                    if os.path.exists(os.path.join(directory, n))]
        if existing:
            answer = QMessageBox.question(self, tr("export.overwrite.title"),
                                          tr("export.overwrite.text", files="\n".join(existing)))
            if answer != QMessageBox.StandardButton.Yes:
                return
        context = dict(self.context, image_format=image_format)
        if "image" in keys:
            draw_image, dark = self.context["draw_image"], not self.light_background.isChecked()
            context["draw_image"] = lambda path: draw_image(path, dark=dark)
        try:
            self.created = Export.export_files(context, keys, directory, prefix)
            self.file_count = len(Export.file_names(keys, prefix, image_format))
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, tr("error.title"), tr("error.export", error=e))
            return
        self.accept()


# ritorna (percorsi creati, numero di file esportati) oppure None se annullato
def run_export_dialog(context: Dict, parent=None) -> Optional[Tuple[List[str], int]]:
    dialog = ExportDialog(context, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.created, dialog.file_count
    return None
