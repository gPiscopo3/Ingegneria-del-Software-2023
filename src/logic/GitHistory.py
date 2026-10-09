import base64
import os
import re
import shutil
import stat
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from requests import HTTPError

from src.i18n import tr
from src.logic import APICalls
from src.logic.APICalls import DATE_FORMAT, BASE_URL, Progress, DownloadCancelled, noreply_author

# i commit si leggono da un clone locale parziale (solo commit e alberi, niente contenuti dei file):
# nessuna quota API, a parte l'associazione email -> account GitHub degli autori

GIT_URL = "https://github.com/"
SHALLOW_MARGIN = timedelta(days=30)  # storia in più clonata prima della data di inizio
CLONE_PROGRESS = re.compile(r"(Counting objects|Compressing objects|Receiving objects|Resolving deltas):\s+(\d+)%")
CLONE_PHASES = {"Counting objects": "progress.clone_counting", "Compressing objects": "progress.clone_compressing",
                "Receiving objects": "progress.clone_receiving", "Resolving deltas": "progress.clone_resolving"}
RECORD, FIELD = "\x1e", "\x1f"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # su Windows git non apre una console


class GitError(Exception):
    pass


def git_available():
    return shutil.which("git") is not None


def refresh_path():
    # su Windows un'app già aperta non vede il PATH aggiornato dall'installer di git: lo rilegge dal registro
    if os.name != "nt":
        return
    import winreg  # pylint: disable=import-outside-toplevel
    sources = [(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
               (winreg.HKEY_CURRENT_USER, "Environment")]
    current = os.environ.get("PATH", "").split(os.pathsep)
    for root, key in sources:
        try:
            with winreg.OpenKey(root, key) as handle:
                value, _ = winreg.QueryValueEx(handle, "Path")
        except OSError:
            continue
        for entry in os.path.expandvars(value).split(os.pathsep):
            if entry and entry not in current:
                current.append(entry)
    os.environ["PATH"] = os.pathsep.join(current)


def git_version() -> Optional[str]:
    if not git_available():
        return None
    try:
        out = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10, check=True,
                             creationflags=_NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"(\d+\.\d+\.\d+)", out)
    return match.group(1) if match else out.strip()


def get_commits_since(owner: str, repo_name: str, starting_date: datetime, token: str, progress: Progress = None,
                      until: Optional[datetime] = None):
    # stesso formato di APICalls.get_commits_since: lista di dict con sha, author, commit.author.date, files
    since = starting_date.strftime(DATE_FORMAT)
    range_options = ["--since=" + since] + (["--until=" + until.strftime(DATE_FORMAT)] if until else [])
    header = APICalls.build_header(token)
    url = GIT_URL + owner + '/' + repo_name + '.git'
    directory = tempfile.mkdtemp(prefix="graphapp-")
    try:
        repo_dir = os.path.join(directory, "repo.git")
        try:
            clone(url, repo_dir, starting_date - SHALLOW_MARGIN, token, progress)
        except GitError as e:
            if "shallow info" in str(e):
                return []  # nessun commit dopo la data di clone, quindi nemmeno nell'intervallo
            raise
        _report(progress, tr("progress.reading_history"))
        # --no-renames: il rilevamento dei rename scaricherebbe uno a uno i contenuti dei file (clone senza blob)
        log_file = os.path.join(directory, "log.txt")
        _run(["git", "-C", repo_dir, "log", "--all", *range_options, "--diff-merges=first-parent", "--no-renames",
              "--name-only", "--format=" + RECORD + "%H" + FIELD + "%ae" + FIELD + "%aI"], log_file)
        with open(log_file, encoding="utf-8", errors="replace") as fp:
            commits = parse_log(fp.read())
        boundary = read_shallow(repo_dir)
    finally:
        shutil.rmtree(directory, onerror=_remove_readonly)

    authors = map_authors(owner, repo_name, since, header, commits, progress, until)

    results = []
    boundary_commits = []
    for sha, email, date, files in commits:
        author = authors.get(email.lower())
        if author is None:
            continue  # autore senza account GitHub: ignorato come con le API
        if sha in boundary:
            boundary_commits.append(sha)  # senza genitore nel clone: i file si chiedono alle API
            continue
        results.append({"sha": sha, "author": author, "commit": {"author": {"date": date}},
                        "files": [{"filename": f} for f in files]})

    def commit_from_api(sha):
        try:
            return APICalls.get_commit(BASE_URL + owner + '/' + repo_name + '/commits/' + sha, header)
        except HTTPError as e:
            print(e.response.text)
            return None

    results.extend(c for c in APICalls.parallel_map(commit_from_api, boundary_commits, progress, tr("progress.boundary_commits"))
                   if c is not None)
    return results


def clone(url: str, destination: str, shallow_since: datetime, token: str, progress: Progress = None):
    # nessuna richiesta di credenziali: né nel terminale né con la finestra di Git Credential Manager, che
    # bloccherebbe il clone finché qualcuno non la chiude; se l'accesso è negato git fallisce e si usano le API
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    if token.strip() != "":
        # autenticazione via variabili d'ambiente: il token non compare nella riga di comando
        credentials = base64.b64encode(("x-access-token:" + token.strip()).encode()).decode()
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader",
                   GIT_CONFIG_VALUE_0="Authorization: Basic " + credentials)
    command = ["git", "-c", "credential.helper=", "clone", "--bare", "--no-single-branch", "--filter=blob:none", "--no-tags", "--progress",
               "--shallow-since=" + shallow_since.strftime("%Y-%m-%d"), url, destination]
    _report(progress, tr("progress.cloning"))
    _run(command, None, env, progress)


# trasforma l'output di git log in (sha, email, data UTC nel formato delle API, file modificati)
def parse_log(text: str) -> List[Tuple[str, str, str, List[str]]]:
    commits = []
    for record in text.split(RECORD):
        if not record.strip():
            continue
        lines = record.split("\n")
        sha, email, date = lines[0].split(FIELD)
        files = [line for line in lines[1:] if line.strip() != ""]
        utc = datetime.fromisoformat(date).astimezone(timezone.utc).strftime(DATE_FORMAT)
        commits.append((sha, email, utc, files))
    return commits


def read_shallow(repo_dir: str) -> set:
    path = os.path.join(repo_dir, "shallow")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as fp:
        return {line.strip() for line in fp if line.strip()}


# email -> {"id", "login"} (None se l'email non è associata a un account GitHub)
def map_authors(owner: str, repo_name: str, since: str, header: Dict[str, str], commits, progress: Progress = None,
                until: Optional[datetime] = None):
    authors: Dict[str, Optional[Dict]] = {}
    sample_sha: Dict[str, str] = {}  # un commit per ogni email, per le email da chiedere alle API
    for sha, email, _, _ in commits:
        key = email.lower()
        if key in authors or key in sample_sha:
            continue
        author = noreply_author(email)
        if author is not None:
            authors[key] = author
        else:
            sample_sha[key] = sha

    # 1) elenco dei commit del branch principale: 100 commit (e relativi autori) per richiesta,
    #    interrotto appena tutte le email sono note
    url = BASE_URL + owner + '/' + repo_name + '/commits?per_page=100&since=' + since
    if until is not None:
        url += '&until=' + until.strftime(DATE_FORMAT)
    while url and any(key not in authors for key in sample_sha):
        response = APICalls.get_with_ratelimit(url, header)
        if response.status_code != 200:
            break
        for item in response.json():
            key = (item.get("commit", {}).get("author", {}).get("email") or "").lower()
            if key in sample_sha and key not in authors:
                author = item.get("author")
                authors[key] = {"id": author["id"], "login": author["login"]} if author else None
        url = APICalls.next_page_url(response)
        _report(progress, tr("progress.commit_authors", done=len(authors),
                                         total=len(authors) + _unknown(authors, sample_sha)))

    # 2) email rimaste (autori presenti solo su altri branch): un solo commit per email
    unknown = [key for key in sample_sha if key not in authors]

    def author_of(key):
        response = APICalls.get_with_ratelimit(BASE_URL + owner + '/' + repo_name + '/commits/' + sample_sha[key],
                                               header)
        # commit sconosciuto a GitHub (404, 422): nessun account; quota esaurita ed errori del server non lo sono
        if response.status_code in (404, 422):
            return None
        response.raise_for_status()
        author = response.json().get("author")
        return {"id": author["id"], "login": author["login"]} if author else None

    for key, author in zip(unknown, APICalls.parallel_map(author_of, unknown, progress, tr("progress.authors"))):
        authors[key] = author
    return authors


def _unknown(authors, sample_sha):
    return sum(1 for key in sample_sha if key not in authors)


def _report(progress: Progress, message: str):
    if progress is not None:
        progress(message, 0, 0)


# esegue git; interrompibile con APICalls.cancel_event, solleva GitError se fallisce
def _run(command: List[str], stdout_path: Optional[str], env=None, progress: Progress = None):
    stdout = open(stdout_path, "wb") if stdout_path else subprocess.DEVNULL  # pylint: disable=consider-using-with
    try:
        process = subprocess.Popen(command, stdout=stdout, stderr=subprocess.PIPE, env=env,  # pylint: disable=consider-using-with
                                   creationflags=_NO_WINDOW)
    except OSError as e:
        if stdout_path:
            stdout.close()
        raise GitError(tr("error.git_run", error=e)) from e

    errors = []

    def read_stderr():
        # git scrive l'avanzamento su stderr separando gli aggiornamenti con \r
        buffer = b""
        for chunk in iter(lambda: process.stderr.read(256), b""):
            buffer += chunk
            *lines, buffer = re.split(rb"[\r\n]", buffer)
            for line in lines:
                text = line.decode(errors="replace").strip()
                match = CLONE_PROGRESS.search(text)
                if match and progress is not None:
                    phase = tr(CLONE_PHASES[match.group(1)])
                    progress(tr("progress.clone_phase", phase=phase, percent=match.group(2)), 0, 0)
                elif text:
                    errors.append(text)

    reader = threading.Thread(target=read_stderr, daemon=True)
    reader.start()
    try:
        while process.poll() is None:
            if APICalls.cancel_event.wait(0.2):
                process.kill()
                process.wait()
                raise DownloadCancelled()
    finally:
        reader.join(timeout=5)
        if stdout_path:
            stdout.close()
    if process.returncode != 0:
        raise GitError("; ".join(errors[-3:]) or tr("error.git_exit", code=process.returncode))


def _remove_readonly(func, path, _):
    # su Windows git crea file in sola lettura che rmtree non riesce a cancellare
    os.chmod(path, stat.S_IWRITE)
    func(path)
