from requests import HTTPError
from typing import Dict, Optional

from requests.exceptions import MissingSchema
from requests.utils import parse_header_links
from datetime import datetime
import requests
import time


DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
API_URL = 'https://api.github.com'
BASE_URL = API_URL + '/repos/'
API_VERSION = '2026-03-10'
DEFAULT_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION}
MAX_RETRIES = 3

# ultimi valori di rate limit letti dagli header delle risposte (usati dalla GUI)
last_rate_limit: Dict[str, int] = {}


def build_header(token: str):
    if not isinstance(token, str):
        raise TypeError("'token' parameter must be str")
    # senza token si usano le richieste non autenticate (60 req/h), con token 5000 req/h
    if token.strip() == "":
        return {}
    return {"Authorization": "Bearer " + token.strip()}


def get_issues_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    header = build_header(token)
    query_string = "?state=all&per_page=100&since=" + starting_date.strftime(DATE_FORMAT)
    issues = []
    results = get_multiple_pages(BASE_URL + owner + '/' + repo_name + '/issues' + query_string, header)
    for issue in results:
        # l'endpoint delle issue restituisce anche le pull request, già gestite da get_pulls_since
        if "pull_request" in issue:
            continue
        comments = dict()
        comments[datetime.strptime(issue["created_at"], DATE_FORMAT)] = issue["user"]
        comments = comments | reformat_response(get_multiple_pages(issue["comments_url"] + "?per_page=100", header))
        comments = dict(sorted(comments.items()))
        issues.append(comments)
    return issues  # lista di dictionary


def get_pulls_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    header = build_header(token)
    pull_requests = []
    query_string = "?state=all&sort=created&direction=desc&per_page=100"
    results = filter_pulls_by_date(BASE_URL + owner + '/' + repo_name + '/pulls' + query_string, header, starting_date)
    for pull in results:

        # vengono presi gli url per accedere a comments, reviews, review comments e commits di una pull request
        # il link alle review è aggiunto a mano perché non c'è nel json di risposta
        urls = list()
        urls.append(BASE_URL + owner + '/' + repo_name + '/pulls/' + str(pull["number"]) + '/reviews?per_page=100')
        for key, url in pull["_links"].items():
            if key == "comments" or key == "review_comments" or key == "commits":
                urls.append(url["href"] + '?per_page=100&since=' + starting_date.strftime(DATE_FORMAT))

        # get su ogni url dei precedenti e fa un "merge" delle risposte, ordinandole per data
        replies = dict()
        replies[datetime.strptime(pull["created_at"], DATE_FORMAT)] = pull["user"]
        for url in urls:
            replies = replies | reformat_response(get_multiple_pages(url, header))
        replies = dict(sorted(replies.items()))
        pull_requests.append(replies)

    return pull_requests  # lista di dictionary


def get_commits_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    header = build_header(token)
    query_string = "?per_page=100"
    commits = []  # lista dove saranno contenuti, mischiati, i commit di ogni branch
    response = get_multiple_pages(BASE_URL + owner + '/' + repo_name + '/branches' + query_string, header)
    query_string += "&since=" + starting_date.strftime(DATE_FORMAT)
    for branch in response:  # prendo tutti i branch
        response = get_multiple_pages(BASE_URL + owner + '/' + repo_name + '/commits' + query_string + "&sha=" +
                                      branch["commit"]["sha"], header)
        for commit in response:  # per ogni branch prendo tutti i commit
            try:
                commits.append(get_commit(commit["url"], header))
            except HTTPError as e:
                print(e.response.text)
    return commits  # lista di dictionary


def get_rate_limit(token: str) -> Optional[Dict[str, int]]:
    # la chiamata a /rate_limit non consuma quota; ritorna None se il token non è valido
    response = requests.get(API_URL + '/rate_limit', headers=DEFAULT_HEADERS | build_header(token), timeout=15)
    if response.status_code != 200:
        return None
    core = response.json()["resources"]["core"]
    return {"limit": core["limit"], "remaining": core["remaining"], "reset": core["reset"]}


# funzioni "private" delle funzioni di sopra

# ritorna la lista delle pulls filtrando per data
def filter_pulls_by_date(url: str, header: Dict[str, str], starting_date: datetime):
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
        return [result for result in results
                if datetime.strptime(result['created_at'], DATE_FORMAT) >= starting_date]  # list
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
        for _ in range(MAX_RETRIES):
            response = requests.get(url, headers=headers, timeout=30)
            update_last_rate_limit(response)
            wait = seconds_to_wait(response)
            if wait is None:
                return response
            print(f"Rate limit raggiunto, attesa di {wait} secondi")
            time.sleep(wait)
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
