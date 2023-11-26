from requests import HTTPError
from model.File import File
from src.model.User import User
from typing import Dict, Set, List
from requests.utils import parse_header_links
from datetime import datetime
import requests
import time


def get_communications_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    base_url = 'https://api.github.com/repos/' + owner + '/' + repo_name
    query_params = '?state=all&sort=updated&direction=desc&since=' + starting_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    header = {"Authorization": "Bearer " + token}

    all_users: Dict[int, User] = {}  # conterrà ogni utente che ha comunicato con le sue relative comunicazioni
    pull_issues: List[int] = []  # conterrà le issue relative alle pull requests, in modo da non controllarle due volte

    # pull requests
    results = get_multiple_pages(base_url + '/pulls' + query_params, header)
    for pull in results:
        pull_issues.append(pull["number"])

        # vengono presi gli url per accedere a comments, reviews, review comments e commits di una pull request
        # il link alle review è aggiunto a mano perché non c'è nel json di risposta
        urls = list()
        urls.append('https://api.github.com/repos/' + owner + '/' + repo_name + '/pulls/' +
                    str(pull["number"]) + '/reviews?state=all&sort=created&direction=asc')
        for key, url in pull["_links"].items():
            if key == "comments" or key == "review_comments" or key == "commits":
                urls.append(url["href"] + '?state=all&sort=created&direction=asc')

        # get su ogni url dei precedenti e fa un "merge" delle risposte, ordinandole per data
        replies = dict()
        for url in urls:
            try:
                response = get_with_ratelimit(url, header)
                response.raise_for_status()
                replies = replies | reformat_response(response.json())
            except HTTPError as e:
                print(e.response.text)
        replies = dict(sorted(replies.items()))

        # prende le comunicazioni avvenute nella pull request
        if communication_happened(replies, pull["user"]["id"]):
            update_communications(replies, all_users, starting_date, pull["user"])

    # issues
    results = get_multiple_pages(base_url + '/issues' + query_params, header)
    for issue in results:
        if issue["number"] not in pull_issues:
            try:
                response = get_with_ratelimit(issue["comments_url"] + '?state=all&sort=created&direction=asc', header)
                response.raise_for_status()
                comments = reformat_response(response.json())
                comments = dict(sorted(comments.items()))
                if communication_happened(comments, issue["user"]["id"]):
                    update_communications(comments, all_users, starting_date, issue["user"])
            except HTTPError as e:
                print(e.response.text)

    # ordina per data (discendente) le comunicazioni di ogni utente
    for key, user in all_users.items():
        user.sort_communications()
    return all_users  # dictionary {user_id: user}, in ogni user ci sono tutte le sue comunicazioni


def get_collaborations_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    header = {"Authorization": "Bearer " + token}
    collaborators: Dict[int, User] = {}
    files: Dict[str, File] = {}
    results = get_multiple_pages("https://api.github.com/repos/" + owner + "/" + repo_name + "/commits?since=" +
                                 starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"), header)
    for item in results:
        try:
            response = get_with_ratelimit(item["url"], header)
            commit = response.json()
            if commit['author'] is not None and "files" in commit:
                if commit['author']['id'] not in collaborators:
                    collaborators[commit['author']['id']] = User(commit['author']['id'], commit['author']['login'])
                for file in commit['files']:
                    if file['filename'] not in files:
                        files[file['filename']] = File(file['filename'])
                    files[file['filename']].add_edit(
                        datetime.strptime(commit['commit']['author']['date'], "%Y-%m-%dT%H:%M:%SZ"),
                        collaborators[commit['author']['id']])
        except HTTPError as e:
            print(e.response.text)
    for sha, file in files.items():
        file.sort_edits()
    return files  # dictionary {file_id: file}, in ogni file ci sono tutte le modifiche avvenute


# effettua una get all'url desiderato prendendo i risultati anche sulle altre pagine (se ci sono)
def get_multiple_pages(url: str, header: Dict[str, str]):
    results = []
    try:
        while url:
            response = get_with_ratelimit(url, header)
            response.raise_for_status()
            results.extend(response.json())
            url = None
            if 'Link' in response.headers:
                links = requests.utils.parse_header_links(response.headers['Link'])
                for link in links:
                    if link['rel'] == 'next':
                        url = link['url']
        return results
    # in caso di errore ritorna una lista vuota
    except HTTPError as e:
        print(e.response.text)
        return []


# richieste get con sleep integrato nel caso si raggiunga il ratelimit
def get_with_ratelimit(url: str, header: Dict[str, str]):
    response = requests.get(url, headers=header)
    # se raggiungo il ratelimit, metto in sleep fino a che non si resetta
    if response.headers.get("x-ratelimit-remaining") == 0:
        now_timestamp = int(time.mktime(datetime.now().timetuple()))
        time.sleep(int(response.headers.get("x-ratelimit-reset")) - now_timestamp)
    return response


# riformatta ogni commento/commit/review in un dictionary con coppie <data: autore>
def reformat_response(response: dict):
    date_format = "%Y-%m-%dT%H:%M:%SZ"
    buffer = dict()
    for item in response:
        if "created_at" in item:
            if item['user'] is not None:
                buffer[datetime.strptime(item["created_at"], date_format)] = item['user']
        elif "submitted_at" in item:
            if item['user'] is not None:
                buffer[datetime.strptime(item["submitted_at"], date_format)] = item['user']
        elif "commit" in item:
            if item['author'] is not None:
                buffer[datetime.strptime(item["commit"]["committer"]["date"], date_format)] = item['author']
    return buffer


# controlla se c'è almeno una risposta di uno user diverso dall'autore della pull request/issue
def communication_happened(response: dict, id_creator: str):
    if len(response) > 0:
        for date, author in response.items():
            if author["id"] != id_creator:
                return True
    return False


# itera le risposte ordinate per data salvando le comunicazioni generate da ogni risposta
def update_communications(response: dict, all_users: Dict[int, User], starting_date: datetime, author: dict):
    previous_users_ids: Set[int] = set()  # buffer in cui sono salvati gli autori delle risposte precedenti

    # aggiunge l'autore della issue / pull request nel buffer
    if author["id"] not in all_users:
        all_users[author["id"]] = User(author["id"], author["login"])
    previous_users_ids.add(author["id"])

    for created_date, sender in response.items():
        if sender["id"] not in all_users:
            all_users[sender["id"]] = User(sender["id"], sender["login"])
        if created_date >= starting_date:  # controlla se risposta è inviata nell'intervallo temporale di interesse
            receivers: Set[User] = set()  # receivers = tutti gli autori delle risposte precedenti*
            for user_id in previous_users_ids:
                if user_id != sender["id"]:  # *tranne se stesso
                    receivers.add(all_users[user_id])
            if len(receivers) > 0:  # se l'utente ha comunicato con almeno un altro utente, aggiungo comunicazioni
                all_users[sender["id"]].update_communication(created_date, receivers)
        previous_users_ids.add(sender["id"])  # aggiunge l'autore della risposta nel buffer
