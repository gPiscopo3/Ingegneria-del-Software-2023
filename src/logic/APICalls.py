from concurrent.futures import ThreadPoolExecutor, FIRST_EXCEPTION, wait
from requests import HTTPError
from typing import Callable, Dict, Iterable, List, Optional

from requests.exceptions import MissingSchema
from requests.utils import parse_header_links
from datetime import datetime
import requests
from src.i18n import tr
import threading
import time


DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
API_URL = 'https://api.github.com'
BASE_URL = API_URL + '/repos/'
API_VERSION = '2026-03-10'
DEFAULT_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION}
MAX_RETRIES = 3
MAX_WORKERS = 8  # richieste contemporanee
MAX_REQUESTS_PER_SECOND = 12  # sotto il limite secondario di GitHub (~900 richieste/minuto)

# callback di avanzamento: (etichetta, elementi completati, totale)
Progress = Optional[Callable[[str, int, int], None]]

# ultimi valori di rate limit letti dagli header delle risposte (usati dalla GUI)
last_rate_limit: Dict[str, int] = {}
_rate_limit_lock = threading.Lock()

# impostato dalla GUI per interrompere un download in corso
cancel_event = threading.Event()

# chiamato con i secondi di attesa quando si raggiunge il rate limit (usato dalla GUI)
rate_limit_listener: Optional[Callable[[int], None]] = None


class DownloadCancelled(Exception):
    pass


class _Throttle:
    # distanzia gli avvii delle richieste di tutti i thread e li mette in pausa insieme in caso di rate limit
    def __init__(self, per_second: float):
        self.interval = 1 / per_second
        self.next_slot = 0.0
        self.pause_until = 0.0
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            slot = max(now, self.next_slot, self.pause_until)
            self.next_slot = slot + self.interval
        if slot > now and cancel_event.wait(slot - now):
            raise DownloadCancelled()

    def pause(self, seconds: int):
        with self.lock:
            self.pause_until = max(self.pause_until, time.monotonic() + seconds)


_throttle = _Throttle(MAX_REQUESTS_PER_SECOND)
_local = threading.local()


def _session():
    # una sessione per thread: riusa le connessioni (keep-alive) senza condividere oggetti non thread-safe
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


# applica func a ogni elemento con più thread; i risultati restano nell'ordine degli elementi
def parallel_map(func: Callable, items: Iterable, progress: Progress = None, label: str = "") -> List:
    items = list(items)
    if not items:
        return []
    results = [None] * len(items)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(func, item): i for i, item in enumerate(items)}
        pending = set(futures)
        done_count = 0
        while pending:
            done, pending = wait(pending, return_when=FIRST_EXCEPTION)
            for future in done:
                if future.exception() is not None:
                    for other in pending:
                        other.cancel()
                    raise future.exception()
                results[futures[future]] = future.result()
                done_count += 1
            if progress is not None:
                progress(label, done_count, len(items))
    return results


def build_header(token: str):
    if not isinstance(token, str):
        raise TypeError("'token' parameter must be str")
    # senza token si usano le richieste non autenticate (60 req/h), con token 5000 req/h
    if token.strip() == "":
        return {}
    return {"Authorization": "Bearer " + token.strip()}


# tutti i commenti del repository di un tipo ("issues" = commenti di issue e PR, "pulls" = commenti di review)
# nell'intervallo [starting_date, until], 100 per richiesta, raggruppati per numero di issue/PR
def get_comments_by_number(owner: str, repo_name: str, kind: str, starting_date: datetime, header: Dict[str, str],
                           progress: Progress = None, until: Optional[datetime] = None) -> Dict[int, list]:
    url_key = "issue_url" if kind == "issues" else "pull_request_url"
    label = tr("progress.comments") if kind == "issues" else tr("progress.review_comments")
    url = (BASE_URL + owner + '/' + repo_name + '/' + kind + '/comments?per_page=100&sort=created&direction=asc'
           '&since=' + starting_date.strftime(DATE_FORMAT))
    grouped: Dict[int, list] = {}
    count = 0
    for comment in get_pages_until(url, header, until):
        number = int(comment[url_key].rsplit('/', 1)[1])
        grouped.setdefault(number, []).append(comment)
        count += 1
    if progress is not None:
        progress(f"{label}: {count}", 0, 0)
    return grouped


def get_issues_since(owner: str, repo_name: str, starting_date: datetime, token: str, progress: Progress = None,
                     issue_comments: Optional[Dict[int, list]] = None, until: Optional[datetime] = None):
    header = build_header(token)
    query_string = "?state=all&per_page=100&sort=created&direction=asc&since=" + starting_date.strftime(DATE_FORMAT)
    results = get_pages_until(BASE_URL + owner + '/' + repo_name + '/issues' + query_string, header, until)
    # l'endpoint delle issue restituisce anche le pull request, già gestite da get_pulls_since
    results = [issue for issue in results if "pull_request" not in issue]
    if issue_comments is None:
        issue_comments = get_comments_by_number(owner, repo_name, "issues", starting_date, header, progress, until)

    issues = []
    for issue in results:
        comments = dict()
        comments[datetime.strptime(issue["created_at"], DATE_FORMAT)] = issue["user"]
        comments = comments | reformat_response(issue_comments.get(issue["number"], []))
        issues.append(dict(sorted(comments.items())))
    return issues  # lista di dictionary


def get_pulls_since(owner: str, repo_name: str, starting_date: datetime, token: str, progress: Progress = None,
                    issue_comments: Optional[Dict[int, list]] = None, until: Optional[datetime] = None):
    header = build_header(token)
    query_string = "?state=all&sort=created&direction=desc&per_page=100"
    results = filter_pulls_by_date(BASE_URL + owner + '/' + repo_name + '/pulls' + query_string, header, starting_date,
                                   until)
    if not results:
        return []
    # commenti e commenti di review presi in blocco per tutto il repository invece che PR per PR
    if issue_comments is None:
        issue_comments = get_comments_by_number(owner, repo_name, "issues", starting_date, header, progress, until)
    review_comments = get_comments_by_number(owner, repo_name, "pulls", starting_date, header, progress, until)

    def pull_replies(pull):
        # per le review e i commit non esiste un endpoint a livello di repository: 2 richieste per PR
        # il link alle review è aggiunto a mano perché non c'è nel json di risposta
        urls = [BASE_URL + owner + '/' + repo_name + '/pulls/' + str(pull["number"]) + '/reviews?per_page=100',
                pull["_links"]["commits"]["href"] + '?per_page=100&since=' + starting_date.strftime(DATE_FORMAT)]

        # "merge" delle risposte, ordinandole per data
        replies = dict()
        replies[datetime.strptime(pull["created_at"], DATE_FORMAT)] = pull["user"]
        replies = replies | reformat_response(issue_comments.get(pull["number"], []))
        replies = replies | reformat_response(review_comments.get(pull["number"], []))
        for url in urls:
            replies = replies | reformat_response(get_multiple_pages(url, header))
        return dict(sorted(replies.items()))

    return parallel_map(pull_replies, results, progress, tr("progress.pull_requests"))  # lista di dictionary


def get_commits_since(owner: str, repo_name: str, starting_date: datetime, token: str, progress: Progress = None,
                      until: Optional[datetime] = None):
    header = build_header(token)
    query_string = "?per_page=100"
    branches = get_multiple_pages(BASE_URL + owner + '/' + repo_name + '/branches' + query_string, header)
    query_string += "&since=" + starting_date.strftime(DATE_FORMAT)
    if until is not None:
        query_string += "&until=" + until.strftime(DATE_FORMAT)

    def branch_commits(branch):
        return get_multiple_pages(BASE_URL + owner + '/' + repo_name + '/commits' + query_string + "&sha=" +
                                  branch["commit"]["sha"], header)

    # un commit raggiungibile da più branch viene scaricato una sola volta
    unique_commits = {}
    for commits_of_branch in parallel_map(branch_commits, branches, progress, tr("progress.branches")):
        for commit in commits_of_branch:
            unique_commits.setdefault(commit["sha"], commit)

    def commit_details(commit):
        try:
            return get_commit(commit["url"], header)
        except HTTPError as e:
            print(e.response.text)
            return None

    details = parallel_map(commit_details, unique_commits.values(), progress, tr("progress.commits"))
    return [commit for commit in details if commit is not None]  # lista di dictionary


def get_rate_limit(token: str) -> Optional[Dict[str, int]]:
    # quota effettiva letta dagli header di una richiesta reale: con alcuni token /rate_limit riporta sempre la
    # quota piena. Con un token si usa /user (costa 1 richiesta e risponde 401 se il token non è valido);
    # senza token /rate_limit, che non consuma quota. Ritorna None se il token non è valido.
    url = API_URL + ('/user' if build_header(token) else '/rate_limit')
    response = _session().get(url, headers=DEFAULT_HEADERS | build_header(token), timeout=15)
    if response.status_code == 401:
        return None
    rate = {}
    for key in ("limit", "remaining", "reset"):
        value = response.headers.get("X-RateLimit-" + key.capitalize())
        if value is None or not value.isdigit():
            response.raise_for_status()  # errore del server senza header di quota
            raise requests.RequestException(tr("error.rate_headers"))
        rate[key] = int(value)
    update_last_rate_limit(response)
    return rate  # presente anche con quota esaurita (403), il token resta valido


# funzioni "private" delle funzioni di sopra

# ritorna la lista delle pulls filtrando per data
def filter_pulls_by_date(url: str, header: Dict[str, str], starting_date: datetime, until: Optional[datetime] = None):
    results = []
    if not isinstance(starting_date, datetime):
        raise TypeError("'starting_date' parameter must be datetime")
    try:
        while url:
            response = get_with_ratelimit(url, header)
            response.raise_for_status()
            page = response.json()
            results.extend(page)
            url = None
            if 'Link' in response.headers and len(page) > 0:
                last_date = datetime.strptime(page[-1]["created_at"], DATE_FORMAT)
                links = parse_header_links(response.headers['Link'])
                for link in links:
                    if link['rel'] == 'next' and last_date > starting_date:
                        url = link['url']
        # le PR create dopo until vengono scartate senza scaricarne review e commit
        return [result for result in results
                if starting_date <= datetime.strptime(result['created_at'], DATE_FORMAT)
                and (until is None or datetime.strptime(result['created_at'], DATE_FORMAT) <= until)]  # list
    except HTTPError as e:
        print(e.response.text)
        return []  # in caso di errore ritorna una lista vuota


# per ogni get request controlla se ci sono altre pagine e unisce tutti i risultati
def get_multiple_pages(url: str, header: Dict[str, str]):
    results = []
    try:
        while url:
            response = get_with_ratelimit(url, header)
            response.raise_for_status()
            results.extend(response.json())
            url = next_page_url(response)
        return results  # list
    except HTTPError as e:
        print(e.response.text)
        return []  # in caso di errore ritorna una lista vuota


# come get_multiple_pages per elenchi ordinati per data di creazione crescente: smette di paginare appena
# supera until (None = fino a oggi), così un periodo passato non scarica tutto fino a oggi
def get_pages_until(url: str, header: Dict[str, str], until: Optional[datetime]):
    if until is None:
        return get_multiple_pages(url, header)
    results = []
    try:
        while url:
            response = get_with_ratelimit(url, header)
            response.raise_for_status()
            page = response.json()
            in_range = [item for item in page if datetime.strptime(item["created_at"], DATE_FORMAT) <= until]
            results.extend(in_range)
            url = next_page_url(response) if len(in_range) == len(page) else None
        return results
    except HTTPError as e:
        print(e.response.text)
        return []  # in caso di errore ritorna una lista vuota


# dettaglio di un commit; oltre 300 file modificati GitHub pagina la lista "files"
def get_commit(url: str, header: Dict[str, str]):
    response = get_with_ratelimit(url, header)
    response.raise_for_status()
    commit = response.json()
    url = next_page_url(response)
    while url:
        response = get_with_ratelimit(url, header)
        response.raise_for_status()
        commit.setdefault("files", []).extend(response.json().get("files", []))
        url = next_page_url(response)
    return commit


def next_page_url(response: requests.Response):
    if 'Link' in response.headers:
        for link in parse_header_links(response.headers['Link']):
            if link['rel'] == 'next':
                return link['url']
    return None


# richieste get con attesa integrata nel caso si raggiunga il ratelimit (primario o secondario)
def get_with_ratelimit(url: str, header: Dict[str, str]):
    headers = header.copy()
    headers.update(DEFAULT_HEADERS)
    try:
        for attempt in range(MAX_RETRIES):
            if cancel_event.is_set():
                raise DownloadCancelled()
            _throttle.acquire()
            try:
                response = _session().get(url, headers=headers, timeout=30)
            except (requests.ConnectionError, requests.Timeout):
                # errore di rete transitorio: si riprova dopo 2, 4… secondi invece di interrompere il download
                if attempt == MAX_RETRIES - 1:
                    raise
                if cancel_event.wait(2 ** (attempt + 1)):
                    raise DownloadCancelled() from None
                continue
            update_last_rate_limit(response)
            seconds = seconds_to_wait(response)
            if seconds is None:
                return response
            print(f"Rate limit raggiunto, attesa di {seconds} secondi")
            _throttle.pause(seconds)  # mette in pausa anche gli altri thread
            if rate_limit_listener is not None:
                rate_limit_listener(seconds)
            if cancel_event.wait(seconds):
                raise DownloadCancelled()
        return response
    except MissingSchema as e:
        print(f"URL Error: {e}")
        # Esempio: solleva un'altra eccezione per gestire l'URL malformato
        raise ValueError("Bad URL") from e


# ritorna i secondi da attendere prima di riprovare, None se la risposta non è limitata
def seconds_to_wait(response: requests.Response):
    if response.status_code not in (403, 429):
        return None
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None and retry_after.isdigit():  # limite secondario
        return int(retry_after)
    if response.headers.get("X-RateLimit-Remaining") == "0":  # limite primario
        reset = int(response.headers.get("X-RateLimit-Reset", "0"))
        return max(0, reset - int(time.time())) + 1
    if response.status_code == 429:
        return 60
    return None  # 403 per altri motivi (es. permessi): non si riprova


def update_last_rate_limit(response: requests.Response):
    with _rate_limit_lock:
        for key in ("limit", "remaining", "reset"):
            value = response.headers.get("X-RateLimit-" + key.capitalize())
            if value is not None and value.isdigit():
                last_rate_limit[key] = int(value)


# riformatta ogni commento/commit/review in un dictionary con coppie <data: autore>
def reformat_response(response: list):
    if not isinstance(response, list):
        raise TypeError("'response' parameter must be list ")

    buffer = dict()
    for item in response:
        if "created_at" in item:
            if item['user'] is not None:
                buffer[datetime.strptime(item["created_at"], DATE_FORMAT)] = item['user']
        elif "submitted_at" in item:
            if item['user'] is not None and item['submitted_at'] is not None:
                buffer[datetime.strptime(item["submitted_at"], DATE_FORMAT)] = item['user']
        elif "commit" in item:
            if item['author'] is not None:
                buffer[datetime.strptime(item["commit"]["committer"]["date"], DATE_FORMAT)] = item['author']
    return buffer
