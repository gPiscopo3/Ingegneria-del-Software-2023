from requests import HTTPError
from typing import Dict
from requests.utils import parse_header_links
from datetime import datetime
import requests
import time


DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
BASE_URL = 'https://api.github.com/repos/'


def get_issues_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    header = {"Authorization": "Bearer " + token}
    query_string = "?state=all&per_page=60&since=" + starting_date.strftime(DATE_FORMAT)
    issues = []
    results = get_multiple_pages(BASE_URL + owner + '/' + repo_name + '/issues' + query_string, header)
    for issue in results:
        comments = dict()
        comments[datetime.strptime(issue["created_at"], DATE_FORMAT)] = issue["user"]
        comments = comments | reformat_response(get_multiple_pages(issue["comments_url"], header))
        comments = dict(sorted(comments.items()))
        issues.append(comments)
    return issues  # lista di dictionary


def get_pulls_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    header = {"Authorization": "Bearer " + token}
    pull_requests = []
    results = pulls_json(owner, repo_name, starting_date, token)
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
    header = {"Authorization": "Bearer " + token}
    query_string = "?per-page=100&since=" + starting_date.strftime(DATE_FORMAT)
    commits = []
    results = get_multiple_pages(BASE_URL + owner + '/' + repo_name + '/commits' + query_string, header)
    for commit in results:
        try:
            response = get_with_ratelimit(commit["url"], header, 0)
            commits.append(response.json())
        except HTTPError as e:
            print(e.response.text)
    return commits  # lista di dictionary


# funzioni "private" delle funzioni di sopra

# ritorna la lista delle pulls filtrando per data
def pulls_json(owner: str, repo_name: str, starting_date: datetime, token: str):
    header = {"Authorization": "Bearer " + token}
    query_string = "?sort=created&direction=desc&per_page=3"
    url = BASE_URL + owner + '/' + repo_name + '/pulls' + query_string
    results = []
    while url:
        response = get_with_ratelimit(url, header, 0)
        results.extend(response.json())
        url = None
        if 'Link' in response.headers:
            links = requests.utils.parse_header_links(response.headers['Link'])
            for link in links:
                ultima_data = datetime.strptime(response.json()[-1]["created_at"], DATE_FORMAT)
                if link['rel'] == 'next' and ultima_data > starting_date:
                    url = link['url']
    return results


# per ogni get request controlla se ci sono altre pagine e unisce tutti i risultati
def get_multiple_pages(url: str, header: Dict[str, str]):
    results = []
    try:
        while url:
            response = get_with_ratelimit(url, header, 0)
            response.raise_for_status()
            results.extend(response.json())
            url = None
            if 'Link' in response.headers:
                links = requests.utils.parse_header_links(response.headers['Link'])
                for link in links:
                    if link['rel'] == 'next':
                        url = link['url']
        return results  # list
    except HTTPError as e:
        print(e.response.text)
        return []  # in caso di errore ritorna una lista vuota


# richieste get con sleep integrato nel caso si raggiunga il ratelimit
def get_with_ratelimit(url: str, header, limit: int):
    response = requests.get(url, headers=header)
    # se raggiungo il ratelimit, metto in sleep fino a che non si resetta
    if int(response.headers.get("X-RateLimit-Remaining")) <= limit:
        now_timestamp = int(time.mktime(datetime.now().timetuple()))
        time.sleep(int(response.headers.get("X-RateLimit-Reset")) - now_timestamp)
    return response


# riformatta ogni commento/commit/review in un dictionary con coppie <data: autore>
def reformat_response(response: list):
    buffer = dict()
    for item in response:
        if "created_at" in item:
            if item['user'] is not None:
                buffer[datetime.strptime(item["created_at"], DATE_FORMAT)] = item['user']
        elif "submitted_at" in item:
            if item['user'] is not None:
                buffer[datetime.strptime(item["submitted_at"], DATE_FORMAT)] = item['user']
        elif "commit" in item:
            if item['author'] is not None:
                buffer[datetime.strptime(item["commit"]["committer"]["date"], DATE_FORMAT)] = item['author']
    return buffer
