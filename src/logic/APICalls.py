from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from requests import HTTPError
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from requests.exceptions import MissingSchema
from requests.utils import parse_header_links
from datetime import datetime
import re
import requests
from src.i18n import tr
import threading
import time


DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
API_URL = 'https://api.github.com'
BASE_URL = API_URL + '/repos/'
API_VERSION = '2026-03-10'
GRAPHQL_URL = API_URL + '/graphql'
GRAPHQL_BATCH = 50  # pull request per query GraphQL
EARLIER_BATCH = 20  # issue/PR per query GraphQL dei commenti precedenti (ognuna porta fino a ~2600 nodi)
DEFAULT_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION}
MAX_RETRIES = 3
MAX_WORKERS = 8  # richieste contemporanee
MAX_REQUESTS_PER_SECOND = 12  # sotto il limite secondario di GitHub (~900 richieste/minuto)
NOREPLY = re.compile(r"^(\d+)\+([^@]+)@users\.noreply\.github\.com$", re.IGNORECASE)

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
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
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


# issue e pull request aggiornate dopo starting_date (con attività nel periodo, anche se create prima) e create
# entro until; le pull request hanno la chiave "pull_request"
def get_issue_listing(owner: str, repo_name: str, starting_date: datetime, header: Dict[str, str],
                      until: Optional[datetime] = None) -> list:
    query_string = "?state=all&per_page=100&sort=created&direction=asc&since=" + starting_date.strftime(DATE_FORMAT)
    return get_pages_until(BASE_URL + owner + '/' + repo_name + '/issues' + query_string, header, until)


def get_issues_since(owner: str, repo_name: str, starting_date: datetime, token: str, progress: Progress = None,
                     issue_comments: Optional[Dict[int, list]] = None, until: Optional[datetime] = None,
                     listing: Optional[list] = None):
    header = build_header(token)
    if listing is None:
        listing = get_issue_listing(owner, repo_name, starting_date, header, until)
    # l'endpoint delle issue restituisce anche le pull request, già gestite da get_pulls_since
    results = [issue for issue in listing if "pull_request" not in issue]
    if issue_comments is None:
        issue_comments = get_comments_by_number(owner, repo_name, "issues", starting_date, header, progress, until)

    issues = []
    for issue in results:
        comments = [(datetime.strptime(issue["created_at"], DATE_FORMAT), issue["user"])]
        comments += reformat_response(issue_comments.get(issue["number"], []))
        issues.append(comments)
    with_earlier_replies(owner, repo_name, [issue["number"] for issue in results], issues, set(), starting_date, until,
                         header, progress)
    return [sort_replies(comments) for comments in issues]  # lista di liste [(data, autore)]


def get_pulls_since(owner: str, repo_name: str, starting_date: datetime, token: str, progress: Progress = None,
                    issue_comments: Optional[Dict[int, list]] = None, until: Optional[datetime] = None,
                    listing: Optional[list] = None):
    header = build_header(token)
    if not isinstance(starting_date, datetime):
        raise TypeError("'starting_date' parameter must be datetime")
    # le PR dall'elenco delle issue: come per le issue contano anche quelle create prima ma attive nel periodo
    # (l'elenco /pulls non si può filtrare per data di aggiornamento)
    if listing is None:
        listing = get_issue_listing(owner, repo_name, starting_date, header, until)
    results = [item for item in listing if "pull_request" in item]
    if not results:
        return []
    # commenti e commenti di review presi in blocco per tutto il repository invece che PR per PR
    if issue_comments is None:
        issue_comments = get_comments_by_number(owner, repo_name, "issues", starting_date, header, progress, until)
    review_comments = get_comments_by_number(owner, repo_name, "pulls", starting_date, header, progress, until)

    # review e commit: senza endpoint a livello di repository; con un token si chiedono con GraphQL, 50 PR per query
    activity = pull_activity(owner, repo_name, [pull["number"] for pull in results], header, progress)

    pulls = []
    for pull in results:
        # "merge" delle risposte, ordinandole per data
        replies = [(datetime.strptime(pull["created_at"], DATE_FORMAT), pull["user"])]
        replies += reformat_response(issue_comments.get(pull["number"], []))
        replies += reformat_response(review_comments.get(pull["number"], []))
        replies += activity[pull["number"]]
        pulls.append(replies)
    numbers = [pull["number"] for pull in results]
    with_earlier_replies(owner, repo_name, numbers, pulls, set(numbers), starting_date, until, header, progress)
    return [sort_replies(replies) for replies in pulls]  # lista di liste [(data, autore)]


# review e commit di ogni PR: {numero: [(data, autore)]}
def pull_activity(owner: str, repo_name: str, numbers: List[int], header: Dict[str, str], progress: Progress = None) \
        -> Dict[int, List[Tuple[datetime, dict]]]:
    if not header:  # senza token GraphQL non è disponibile: 2 richieste REST per PR
        replies = parallel_map(lambda number: rest_pull_replies(owner, repo_name, number, header), numbers, progress,
                               tr("progress.pull_requests"))
        return dict(zip(numbers, replies))

    batches = [numbers[i:i + GRAPHQL_BATCH] for i in range(0, len(numbers), GRAPHQL_BATCH)]

    def scaled(label, done, _total):  # avanzamento in PR e non in gruppi di PR
        if progress is not None:
            progress(label, min(done * GRAPHQL_BATCH, len(numbers)), len(numbers))

    activity: Dict[int, List[Tuple[datetime, dict]]] = {}
    for batch_result in parallel_map(lambda batch: graphql_pull_activity(owner, repo_name, batch, header), batches,
                                     scaled, tr("progress.pull_requests")):
        activity.update(batch_result)
    return activity


def rest_pull_replies(owner: str, repo_name: str, number: int, header: Dict[str, str]):
    # tutti i commit della PR: quelli prima di starting_date contano come interventi precedenti
    pull_url = BASE_URL + owner + '/' + repo_name + '/pulls/' + str(number)
    replies = []
    for url in (pull_url + '/reviews?per_page=100', pull_url + '/commits?per_page=100'):
        replies += reformat_response(get_multiple_pages(url, header))
    return replies


PULL_FIELDS = """
    reviews(first: 100) { pageInfo { hasNextPage } nodes { submittedAt
        author { __typename login ... on User { databaseId } ... on Bot { databaseId } } } }
    commits(first: 100) { pageInfo { hasNextPage } nodes { commit { committedDate
        author { email user { databaseId login } } } } }"""


# review e commit di un gruppo di PR con una sola query GraphQL; le PR che GraphQL non restituisce per intero
# (più di 100 review o commit, PR non trovata) o l'intero gruppo se la richiesta fallisce passano da REST
def graphql_pull_activity(owner: str, repo_name: str, numbers: List[int], header: Dict[str, str]):
    query = ("query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { " +
             " ".join(f"p{n}: pullRequest(number: {n}) {{ {PULL_FIELDS} }}" for n in numbers) + " } }")
    try:
        body = post_graphql(query, {"owner": owner, "name": repo_name}, header)
        repository = (body.get("data") or {}).get("repository") or {}
    except HTTPError:
        repository = {}

    activity = {}
    for number in numbers:
        replies = graphql_replies(repository.get(f"p{number}"))
        if replies is None:
            replies = rest_pull_replies(owner, repo_name, number, header)
        activity[number] = replies
    return activity


# converte la risposta GraphQL di una PR nel formato di reformat_response; None se non è completa
def graphql_replies(pull: Optional[dict]) -> Optional[List[Tuple[datetime, dict]]]:
    if pull is None or pull["reviews"]["pageInfo"]["hasNextPage"] or pull["commits"]["pageInfo"]["hasNextPage"]:
        return None
    replies = []
    for review in pull["reviews"]["nodes"]:
        author = review.get("author")
        if review.get("submittedAt") is None or author is None or author.get("databaseId") is None:
            continue
        login = author["login"] + ("[bot]" if author["__typename"] == "Bot" else "")  # come nelle API REST
        replies.append((datetime.strptime(review["submittedAt"], DATE_FORMAT),
                        {"id": author["databaseId"], "login": login}))
    for node in pull["commits"]["nodes"]:
        commit = node["commit"]
        commit_author = commit.get("author") or {}
        user = commit_author.get("user")
        if user is not None and user.get("databaseId") is not None:
            author = {"id": user["databaseId"], "login": user["login"]}
        else:
            author = noreply_author(commit_author.get("email") or "")  # bot e account senza profilo collegato
        if author is not None:
            replies.append((datetime.strptime(commit["committedDate"], DATE_FORMAT), author))
    return replies


# aggiunge a replies_lists (una lista di risposte per ogni numero) i commenti precedenti a starting_date delle issue/PR
# create prima dell'intervallo che hanno almeno una risposta al suo interno: sono le uniche a cui possono rispondere
# i commenti dell'intervallo, e il blocco dei commenti scaricato con "since" non li comprende
def with_earlier_replies(owner: str, repo_name: str, numbers: List[int], replies_lists: List[list], pulls: Set[int],
                         starting_date: datetime, until: Optional[datetime], header: Dict[str, str],
                         progress: Progress = None):
    old = [number for number, replies in zip(numbers, replies_lists)
           if replies[0][0] < starting_date and has_reply_in_range(replies, starting_date, until)]
    earlier = earlier_replies(owner, repo_name, old, pulls, starting_date, header, progress)
    for number, replies in zip(numbers, replies_lists):
        replies.extend(earlier.get(number, []))


def has_reply_in_range(replies: List[Tuple[datetime, dict]], starting_date: datetime, until: Optional[datetime] = None):
    return any(date >= starting_date and (until is None or date <= until) for date, _ in replies)


# risposte (data, autore) precedenti a starting_date di issue e PR: commenti e, per le PR, commenti di review;
# review e commit delle PR arrivano già per intero da pull_activity. Con un token si usa GraphQL, EARLIER_BATCH
# elementi per query; senza token 1 o 2 richieste REST per elemento
def earlier_replies(owner: str, repo_name: str, numbers: List[int], pulls: Set[int], starting_date: datetime,
                    header: Dict[str, str], progress: Progress = None) -> Dict[int, List[Tuple[datetime, dict]]]:
    if not numbers:
        return {}
    label = tr("progress.comments")
    if not header:
        replies = parallel_map(lambda number: rest_earlier_replies(owner, repo_name, number, number in pulls,
                                                                   starting_date, header), numbers, progress, label)
        return dict(zip(numbers, replies))

    batches = [numbers[i:i + EARLIER_BATCH] for i in range(0, len(numbers), EARLIER_BATCH)]

    def scaled(batch_label, done, _total):  # avanzamento in elementi e non in gruppi
        if progress is not None:
            progress(batch_label, min(done * EARLIER_BATCH, len(numbers)), len(numbers))

    earlier: Dict[int, List[Tuple[datetime, dict]]] = {}
    for batch_result in parallel_map(lambda batch: graphql_earlier_replies(owner, repo_name, batch, pulls,
                                                                           starting_date, header),
                                     batches, scaled, label):
        earlier.update(batch_result)
    return earlier


def rest_earlier_replies(owner: str, repo_name: str, number: int, is_pull: bool, starting_date: datetime,
                         header: Dict[str, str]) -> List[Tuple[datetime, dict]]:
    base = BASE_URL + owner + '/' + repo_name
    urls = [f"{base}/issues/{number}/comments?per_page=100"]
    if is_pull:
        urls.append(f"{base}/pulls/{number}/comments?per_page=100")
    replies = []
    for url in urls:
        replies += reformat_response(get_multiple_pages(url, header))
    return [reply for reply in replies if reply[0] < starting_date]


COMMENT_FIELDS = ("pageInfo { hasNextPage } nodes { createdAt "
                  "author { __typename login ... on User { databaseId } ... on Bot { databaseId } } }")
EARLIER_FIELDS = ("__typename ... on Issue { comments(first: 100) { " + COMMENT_FIELDS + " } } "
                  "... on PullRequest { comments(first: 100) { " + COMMENT_FIELDS + " } "
                  "reviewThreads(first: 50) { pageInfo { hasNextPage } nodes { comments(first: 50) { " +
                  COMMENT_FIELDS + " } } } }")


# come earlier_replies per un gruppo di numeri con una sola query GraphQL; gli elementi che GraphQL non restituisce
# per intero (troppi commenti o thread di review) o l'intero gruppo se la richiesta fallisce passano da REST
def graphql_earlier_replies(owner: str, repo_name: str, numbers: List[int], pulls: Set[int], starting_date: datetime,
                            header: Dict[str, str]) -> Dict[int, List[Tuple[datetime, dict]]]:
    query = ("query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { " +
             " ".join(f"n{n}: issueOrPullRequest(number: {n}) {{ {EARLIER_FIELDS} }}" for n in numbers) + " } }")
    try:
        body = post_graphql(query, {"owner": owner, "name": repo_name}, header)
        repository = (body.get("data") or {}).get("repository") or {}
    except HTTPError:
        repository = {}

    earlier = {}
    for number in numbers:
        replies = graphql_earlier(repository.get(f"n{number}"), starting_date)
        if replies is None:
            replies = rest_earlier_replies(owner, repo_name, number, number in pulls, starting_date, header)
        earlier[number] = replies
    return earlier


# risposte precedenti a starting_date nella risposta GraphQL di un'issue/PR; None se non è completa. I commenti
# arrivano in ordine di creazione: se l'ultimo ricevuto è già successivo all'inizio, quelli precedenti ci sono tutti
def graphql_earlier(item: Optional[dict], starting_date: datetime) -> Optional[List[Tuple[datetime, dict]]]:
    if item is None:
        return None
    comments = item["comments"]
    nodes = comments["nodes"]
    if comments["pageInfo"]["hasNextPage"] and (not nodes or
                                                datetime.strptime(nodes[-1]["createdAt"], DATE_FORMAT) < starting_date):
        return None
    groups = [nodes]
    threads = item.get("reviewThreads")
    if threads is not None:
        if threads["pageInfo"]["hasNextPage"]:
            return None
        for thread in threads["nodes"]:
            if thread["comments"]["pageInfo"]["hasNextPage"]:
                return None
            groups.append(thread["comments"]["nodes"])
    replies = []
    for node in (node for group in groups for node in group):
        date = datetime.strptime(node["createdAt"], DATE_FORMAT)
        author = graphql_user(node.get("author"))
        if author is not None and date < starting_date:
            replies.append((date, author))
    return replies


# autore GraphQL nel formato delle API REST; None per account eliminati o senza id
def graphql_user(author: Optional[dict]) -> Optional[dict]:
    if author is None or author.get("databaseId") is None:
        return None
    return {"id": author["databaseId"], "login": author["login"] + ("[bot]" if author["__typename"] == "Bot" else "")}


def noreply_author(email: str) -> Optional[Dict]:
    match = NOREPLY.match(email)
    if match is None:
        return None
    return {"id": int(match.group(1)), "login": match.group(2)}


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
        return empty_if_not_found(e)


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
        return empty_if_not_found(e)


# repository o token inesistenti (404, 401) danno una lista vuota; quota esaurita (403, 429) ed errori del server
# (5xx) vengono propagati, altrimenti un download fallito sembrerebbe un periodo senza attività
def empty_if_not_found(error: HTTPError):
    if error.response is None or error.response.status_code not in (401, 404):
        raise error
    print(error.response.text)
    return []


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
    return _request_with_ratelimit(url, header)


# query GraphQL (POST); oltre ai limiti di get_with_ratelimit gestisce quello primario di GraphQL, che GitHub
# segnala con HTTP 200 e un errore RATE_LIMITED. Solleva HTTPError se la richiesta fallisce
def post_graphql(query: str, variables: dict, header: Dict[str, str]) -> dict:
    body = {}
    for _ in range(MAX_RETRIES):
        response = _request_with_ratelimit(GRAPHQL_URL, header, {"query": query, "variables": variables})
        response.raise_for_status()
        body = response.json()
        if not any(error.get("type") == "RATE_LIMITED" for error in body.get("errors") or []):
            return body
        seconds = max(0, int(response.headers.get("X-RateLimit-Reset", "0")) - int(time.time())) + 1
        print(f"Rate limit GraphQL raggiunto, attesa di {seconds} secondi")
        _throttle.pause(seconds)
        if rate_limit_listener is not None:
            rate_limit_listener(seconds)
        if cancel_event.wait(seconds):
            raise DownloadCancelled()
    return body


def _request_with_ratelimit(url: str, header: Dict[str, str], payload: Optional[dict] = None):
    headers = header.copy()
    headers.update(DEFAULT_HEADERS)
    try:
        for attempt in range(MAX_RETRIES):
            if cancel_event.is_set():
                raise DownloadCancelled()
            _throttle.acquire()
            try:
                if payload is None:
                    response = _session().get(url, headers=headers, timeout=30)
                else:
                    response = _session().post(url, headers=headers, json=payload, timeout=30)
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
    if response.headers.get("X-RateLimit-Resource") == "graphql":
        return  # la GUI mostra la quota REST, quella di GraphQL è separata
    with _rate_limit_lock:
        for key in ("limit", "remaining", "reset"):
            value = response.headers.get("X-RateLimit-" + key.capitalize())
            if value is not None and value.isdigit():
                last_rate_limit[key] = int(value)


# riformatta ogni commento/commit/review in una lista di coppie (data, autore); una lista e non un dict per data:
# due risposte nello stesso secondo restano entrambe
def reformat_response(response: list) -> List[Tuple[datetime, dict]]:
    if not isinstance(response, list):
        raise TypeError("'response' parameter must be list ")

    buffer = []
    for item in response:
        if "created_at" in item:
            if item['user'] is not None:
                buffer.append((datetime.strptime(item["created_at"], DATE_FORMAT), item['user']))
        elif "submitted_at" in item:
            if item['user'] is not None and item['submitted_at'] is not None:
                buffer.append((datetime.strptime(item["submitted_at"], DATE_FORMAT), item['user']))
        elif "commit" in item:
            if item['author'] is not None:
                buffer.append((datetime.strptime(item["commit"]["committer"]["date"], DATE_FORMAT), item['author']))
    return buffer


# ordina le risposte per data; l'ordinamento è stabile, quindi a parità di data l'apertura della issue/PR
# (sempre il primo elemento) resta prima
def sort_replies(replies: List[Tuple[datetime, dict]]) -> List[Tuple[datetime, dict]]:
    return sorted(replies, key=lambda reply: reply[0])
