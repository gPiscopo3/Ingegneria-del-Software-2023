from model.File import File
from src.model.User import User
from typing import Dict, Set, List
from requests.utils import parse_header_links
from datetime import datetime
import requests


def get_communications_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    all_users: Dict[int, User] = {}  # conterrà ogni utente che ha comunicato con le sue relative comunicazioni
    header = {"Authorization": "Bearer " + token}
    pull_issues: List[int] = []  # conterrà le issue relative alle pull requests, in modo da non controllarle due volte

    # pull requests
    results = get_multiple_pages('https://api.github.com/repos/' + owner + '/' + repo_name + '/pulls' + '?state=all&'
                                 'sort=updated&direction=desc&since=' + starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 header)

    if isinstance(results, list):
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
                response = requests.get(url, headers=header)
                if response.status_code == 200:
                    replies = replies | reformat_response(response.json())
                else:
                    print(response.status_code)
            replies = dict(sorted(replies.items()))

            # prende le comunicazioni avvenute nella pull request
            if communication_happened(replies, pull["user"]["id"]):
                update_communications(replies, all_users, starting_date, pull["user"])
    else:
        print(results)

    # issues
    results = get_multiple_pages('https://api.github.com/repos/' + owner + '/' + repo_name + '/issues' + '?state=all&'
                                 'sort=updated&direction=desc&since=' + starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 header)
    if isinstance(results, list):
        for issue in results:
            if issue["number"] not in pull_issues:
                response = requests.get(issue["comments_url"] + '?state=all&sort=created&direction=asc', headers=header)
                if response.status_code == 200:
                    comments = reformat_response(response.json())
                    comments = dict(sorted(comments.items()))
                    if communication_happened(comments, issue["user"]["id"]):
                        update_communications(comments, all_users, starting_date, issue["user"])
                else:
                    print(response.status_code)
    else:
        print(results)

    # ordina per data (discendente) le comunicazioni di ogni utente
    for key, user in all_users.items():
        user.sort_communications()
    return all_users


def get_collaborations_since(starting_date: datetime, owner: str, repo_name: str, token: str):
    header = {"Authorization": "Bearer " + token}
    collaborators: Dict[int, User] = {}
    files: Dict[str, File] = {}
    response = requests.get('https://api.github.com/repos/' + owner + '/' + repo_name + '/collaborators')
    if response.status_code == 200:
        for collaborator in response.json():
            collaborators[collaborator["id"]] = User(collaborator["id"], collaborator["login"])
        results = get_multiple_pages("https://api.github.com/repos/" + owner + "/" + repo_name + "/commits?since=" +
                                     starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"), header)
        if isinstance(results, list):
            for item in results:
                response = requests.get(item["commit"]["url"], headers=header)
                if response.status_code == 200:
                    commit = response.json()
                    if commit['author'] is not None:
                        for file in commit['files']:
                            if file["sha"] not in files:
                                files[file["sha"]] = File(file["sha"])
                            files[file["sha"]].add_edit(commit['commit']['author']['date'],
                                                        collaborators[commit['author']['id']])
                else:
                    print(response.status_code)
            else:
                print(results)
    else:
        print(response.status_code)
    for sha, file in files.items():
        file.sort_edits()
    return files


# effettua una get all'url desiderato prendendo i risultati anche sulle altre pagine (se ci sono)
def get_multiple_pages(url: str, header: Dict[str, str]):
    results = []
    while url:
        response = requests.get(url, headers=header)
        if response.status_code != 200:
            return response.status_code
        if isinstance(response.json(), list):
            results.extend(response.json())
        url = None
        if 'Link' in response.headers:
            links = requests.utils.parse_header_links(response.headers['Link'])
            for link in links:
                if link['rel'] == 'next':
                    url = link['url']
    return results


# riformatta ogni commento/commit/review in un dictionary con coppie <data: autore>
def reformat_response(response: dict):
    buffer = dict()
    for item in response:
        if "created_at" in item:
            if item['user'] is not None:
                buffer[datetime.strptime(item["created_at"], "%Y-%m-%dT%H:%M:%SZ")] = item['user']
        elif "submitted_at" in item:
            if item['user'] is not None:
                buffer[datetime.strptime(item["submitted_at"], "%Y-%m-%dT%H:%M:%SZ")] = item['user']
        elif "commit" in item:
            if item['author'] is not None:
                buffer[datetime.strptime(item["commit"]["committer"]["date"], "%Y-%m-%dT%H:%M:%SZ")] = item['author']
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