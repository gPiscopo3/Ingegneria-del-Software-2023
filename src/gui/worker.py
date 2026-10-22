import threading
import time
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from src.i18n import tr, format_number
from src.logic import APICalls
from src.logic.DataManagement import get_collaborations_since, get_communications_since

PROGRESS_INTERVAL = 0.1  # al massimo ~10 aggiornamenti al secondo verso la GUI


# scarica da GitHub, in un QThread separato, solo le parti di dati che mancano
class DownloadWorker(QObject):
    progress = pyqtSignal(str)
    rate_limited = pyqtSignal(int)  # secondi di attesa
    part_done = pyqtSignal(str, object)  # "files" (collaborazioni) o "users" (comunicazioni), dati
    finished = pyqtSignal()
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    # scarica solo l'intervallo [starting_date, until] (until None = fino a oggi)
    def __init__(self, owner: str, repo: str, starting_date: datetime, until: Optional[datetime], token: str,
                 need_files: bool, need_users: bool):
        super().__init__()
        self.owner = owner
        self.repo = repo
        self.starting_date = starting_date
        self.until = until
        self.token = token
        self.need_files = need_files
        self.need_users = need_users
        self.phase = ""
        self.last_emit = 0.0
        self.lock = threading.Lock()

    # chiamata dai thread del pool: i segnali vengono consegnati in coda al thread della GUI
    def report(self, label: str, done: int, total: int):
        # total == 0: messaggio senza contatore (es. "clone del repository: ricezione oggetti 45%")
        with self.lock:
            now = time.monotonic()
            last_step = total > 0 and done == total
            if not last_step and now - self.last_emit < PROGRESS_INTERVAL:
                return
            self.last_emit = now
        if total == 0:
            self.progress.emit(f"{self.phase} · {label}")
        else:
            self.progress.emit(f"{self.phase} · {label} {format_number(done)}/{format_number(total)}")

    def run(self):
        APICalls.cancel_event.clear()
        APICalls.rate_limit_listener = self.rate_limited.emit
        try:
            if self.need_files:
                self.phase = tr("progress.collaborations")
                self.progress.emit(f"{self.phase} · {tr('progress.starting')}")
                files = get_collaborations_since(self.owner, self.repo, self.starting_date, self.token, self.report,
                                                 self.until)
                self.part_done.emit("files", files)
            if self.need_users:
                self.phase = tr("progress.communications")
                self.progress.emit(f"{self.phase} · {tr('progress.communications_start')}")
                users = get_communications_since(self.owner, self.repo, self.starting_date, self.token, self.report,
                                                 self.until)
                self.part_done.emit("users", users)
        except APICalls.DownloadCancelled:
            self.cancelled.emit()
            return
        except Exception as e:  # pylint: disable=broad-except
            self.failed.emit(str(e))
            return
        finally:
            APICalls.rate_limit_listener = None
        self.finished.emit()
