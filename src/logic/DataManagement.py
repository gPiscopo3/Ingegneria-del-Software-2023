from src.model.File import File
from src.model.User import User
from typing import Dict, Optional, Set, Tuple
from datetime import datetime
from src.logic import APICalls, GitHistory
import pickle


# commit dal clone locale (nessuna quota API); senza git, o se il clone non riesce, dalle API (1 richiesta per commit)
def fetch_commits(owner: str, repo_name: str, starting_date: datetime, token: str,
                  progress: APICalls.Progress = None, until: Optional[datetime] = None):
    if GitHistory.git_available():
        try:
            return GitHistory.get_commits_since(owner, repo_name, starting_date, token, progress, until)
        except GitHistory.GitError as e:
            print(f"Clone non riuscito ({e}), uso delle API")
            if progress is not None:
                progress("clone non riuscito, uso delle API…", 0, 0)
    return APICalls.get_commits_since(owner, repo_name, starting_date, token, progress, until)


# dati scaricati solo nell'intervallo [starting_date, until] (until None = fino a oggi)
def get_communications_since(owner: str, repo_name: str, starting_date: datetime, token: str,
                             progress: APICalls.Progress = None, until: Optional[datetime] = None):
    all_users: Dict[int, User] = {}  # conterrà ogni utente che ha comunicato con le sue relative comunicazioni
    if not isinstance(starting_date, datetime):
        raise TypeError("'starting_date' parameter must be datetime")

    # commenti di issue e pull request, scaricati una sola volta in blocco per tutto il repository
    issue_comments = APICalls.get_comments_by_number(owner, repo_name, "issues", starting_date,
                                                     APICalls.build_header(token), progress, until)

    # pull requests
    results = APICalls.get_pulls_since(owner, repo_name, starting_date, token, progress, issue_comments, until)
    for pull in results:
        if communication_happened(pull):
            update_communications(pull, all_users, starting_date, until)

    # issues
    results = APICalls.get_issues_since(owner, repo_name, starting_date, token, progress, issue_comments, until)
    for issue in results:
        if communication_happened(issue):
            update_communications(issue, all_users, starting_date, until)

    for key, user in all_users.items():  # ordina per data (discendente) le comunicazioni di ogni utente
        user.sort_communications()

    return all_users  # dictionary {user_id: user}, in ogni user ci sono tutte le sue comunicazioni


def get_collaborations_since(owner: str, repo_name: str, starting_date: datetime, token: str,
                             progress: APICalls.Progress = None, until: Optional[datetime] = None):
    collaborators: Dict[int, User] = {}  # conterrà la lista degli utenti che hanno commitato
    files: Dict[str, File] = {}  # conterrà ogni file presente nei commit e coppie data:autore per ogni modifica

    results = fetch_commits(owner, repo_name, starting_date, token, progress, until)
    for commit in results:
        if commit['author'] is not None and "files" in commit:

            if commit['author']['id'] not in collaborators:  # crea l'utente se non è già presente in collaborators
                collaborators[commit['author']['id']] = User(commit['author']['id'], commit['author']['login'])

            for file in commit['files']:
                if file['filename'] not in files:  # crea il file se non è già presente in files
                    files[file['filename']] = File(file['filename'])
                files[file['filename']].add_edit(
                    datetime.strptime(commit['commit']['author']['date'], "%Y-%m-%dT%H:%M:%SZ"),
                    collaborators[commit['author']['id']])

    for sha, file in files.items():  # ordina per data (discendente) le modifiche di ogni file
        file.sort_edits()

    return files  # dictionary {file_id: file}, in ogni file ci sono tutte le modifiche avvenute


# salvataggio e caricamento espliciti dei dati di un repository (file scelto dall'utente)

DATA_FORMAT = "graphapp-data"
DATA_VERSION = 1
DATA_EXTENSION = ".graphapp"

# uniche classi che un file di dati può contenere: caricare un pickle arbitrario eseguirebbe codice
ALLOWED_CLASSES = {
    ("src.model.User", "User"): User,
    ("src.model.File", "File"): File,
    ("datetime", "datetime"): datetime,
    ("builtins", "set"): set,
    ("builtins", "frozenset"): frozenset,
}


class _RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in ALLOWED_CLASSES:
            return ALLOWED_CLASSES[(module, name)]
        raise pickle.UnpicklingError(f"classe non consentita: {module}.{name}")


Range = Tuple[datetime, datetime]


# files_range / users_range: intervallo (inizio, fine) in cui è stata scaricata ciascuna parte
def save_data(path: str, owner: str, repo_name: str, starting_date: datetime,
              files: Optional[Dict[str, File]], users: Optional[Dict[int, User]],
              files_range: Optional[Range] = None, users_range: Optional[Range] = None):
    if files is None and users is None:
        raise ValueError("Nessun dato da salvare.")
    saved_at = datetime.now().replace(microsecond=0)
    ranges = [r for r, part in ((files_range, files), (users_range, users)) if r is not None and part is not None]
    data = {
        "format": DATA_FORMAT,
        "version": DATA_VERSION,
        "owner": owner,
        "repo": repo_name,
        "starting_date": min(r[0] for r in ranges) if ranges else starting_date,
        "ending_date": max(r[1] for r in ranges) if ranges else saved_at,
        "saved_at": saved_at,
        "files": files,  # collaborazioni
        "users": users,  # comunicazioni
        "files_range": files_range if files is not None else None,
        "users_range": users_range if users is not None else None,
    }
    # un unico dump: gli utenti condivisi tra più file/comunicazioni restano lo stesso oggetto
    with open(path, 'wb') as fp:
        pickle.dump(data, fp, protocol=pickle.HIGHEST_PROTOCOL)


def load_data(path: str):
    try:
        with open(path, 'rb') as fp:
            data = _RestrictedUnpickler(fp).load()
    except (pickle.UnpicklingError, EOFError, AttributeError, ValueError, TypeError, IndexError) as e:
        raise ValueError(f"File non valido: non contiene dati di GraphApp ({e}).") from e

    if not isinstance(data, dict) or data.get("format") != DATA_FORMAT:
        raise ValueError("File non valido: non contiene dati di GraphApp.")
    if data.get("version") != DATA_VERSION:
        raise ValueError(f"Versione del file non supportata: {data.get('version')}.")
    for key in ("owner", "repo"):
        if not isinstance(data.get(key), str) or data[key] == "":
            raise ValueError(f"File non valido: campo «{key}» mancante.")
    for key in ("files", "users"):
        if data.get(key) is not None and not isinstance(data[key], dict):
            raise ValueError(f"File non valido: campo «{key}» malformato.")
    if data.get("files") is None and data.get("users") is None:
        raise ValueError("File non valido: non contiene né collaborazioni né comunicazioni.")

    # file salvati prima dell'introduzione degli intervalli: valgono da starting_date al salvataggio
    start, end = data.get("starting_date"), data.get("ending_date") or data.get("saved_at")
    fallback = (start, end) if _is_range((start, end)) else None
    data["ending_date"] = end
    for part, key in (("files", "files_range"), ("users", "users_range")):
        value = data.get(key)
        data[key] = None if data[part] is None else (tuple(value) if _is_range(value) else fallback)
    return data


def _is_range(value):
    return (isinstance(value, (tuple, list)) and len(value) == 2
            and all(isinstance(d, datetime) for d in value) and value[0] <= value[1])


# periodo (data minima, data massima) in cui ci sono modifiche ai file o comunicazioni; None se non ce ne sono
def activity_period(files: Optional[Dict[str, File]], users: Optional[Dict[int, User]]) \
        -> Optional[Tuple[datetime, datetime]]:
    dates = []
    for file in (files or {}).values():
        dates.extend(file.modified_by.keys())
    for user in (users or {}).values():
        dates.extend(user.communications.keys())
    if not dates:
        return None
    return min(dates), max(dates)


# funzioni "private" delle funzioni di sopra

# controlla se c'è almeno una risposta di uno user diverso dall'autore della pull request/issue
def communication_happened(response: dict):
    if len(response) > 0:
        id_creator = next(iter(response.values()))['id']
        for date, author in response.items():
            if author["id"] != id_creator:
                return True
    return False


# itera le risposte ordinate per data salvando le comunicazioni generate da ogni risposta
def update_communications(response: dict, all_users: Dict[int, User], starting_date: datetime,
                          until: Optional[datetime] = None):
    previous_users_ids: Set[int] = set()  # buffer in cui sono salvati gli autori delle risposte precedenti
    for created_date, sender in response.items():

        if sender["id"] not in all_users:  # crea l'utente se non è già presente in all_users
            all_users[sender["id"]] = User(sender["id"], sender["login"])

        # controlla se risposta è inviata nell'intervallo temporale di interesse
        if created_date >= starting_date and (until is None or created_date <= until):

            receivers: Set[User] = set()  # receivers = tutti gli autori delle risposte precedenti*
            for user_id in previous_users_ids:
                if user_id != sender["id"]:  # *tranne se stesso
                    receivers.add(all_users[user_id])

            if len(receivers) > 0:  # se l'utente ha comunicato con almeno un altro utente, aggiungo comunicazioni
                all_users[sender["id"]].update_communication(created_date, receivers)

        previous_users_ids.add(sender["id"])  # aggiunge l'autore della risposta nel buffer
