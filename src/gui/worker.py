import threading
import time
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from src.logic import APICalls
from src.logic.DataManagement import get_collaborations_since, get_communications_since

PROGRESS_INTERVAL = 0.1  # al massimo ~10 aggiornamenti al secondo verso la GUI


def format_number(n: int):
    return f"{n:,}".replace(",", ".")


# scarica da GitHub, in un QThread separato, solo le parti di dati che mancano
class DownloadWorker(QObject):
    progress = pyqtSignal(str)
    rate_limited = pyqtSignal(int)  # secondi di attesa
    part_done = pyqtSignal(str, object)  # "files" (collaborazioni) o "users" (comunicazioni), dati
    finished = pyqtSignal()
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, owner: str, repo: str, starting_date: datetime, token: str, need_files: bool,
                 need_users: bool):
        super().__init__()
        self.owner = owner
        self.repo = repo
        self.starting_date = starting_date
        self.token = token
        self.need_files = need_files
        self.need_users = need_users
        self.phase = ""
        self.last_emit = 0.0
        self.lock = threading.Lock()

    # chiamata dai thread del pool: i segnali vengono consegnati in coda al thread della GUI
    def report(self, label: str, done: int, total: int):
        with self.lock:
            now = time.monotonic()
            if done < total and now - self.last_emit < PROGRESS_INTERVAL:
                return
            self.last_emit = now
        self.progress.emit(f"{self.phase} · {label} {format_number(done)}/{format_number(total)}")

    def run(self):
        APICalls.cancel_event.clear()
        APICalls.rate_limit_listener = self.rate_limited.emit
        try:
            if self.need_files:
                self.phase = "Collaborazioni"
                self.progress.emit("Collaborazioni · elenco dei branch e dei commit…")
                files = get_collaborations_since(self.owner, self.repo, self.starting_date, self.token, self.report)
                self.part_done.emit("files", files)
            if self.need_users:
                self.phase = "Comunicazioni"
                self.progress.emit("Comunicazioni · elenco di pull request e issue…")
                users = get_communications_since(self.owner, self.repo, self.starting_date, self.token, self.report)
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
