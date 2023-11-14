from src.model.User import User
from typing import Dict, Set
from datetime import datetime
import requests


# TO DO: aggiungere commits (capire perché non funzionano)
def get_communications(owner: str, repo_name: str, starting_date: datetime, token: str):
    all_users: Dict[int, User] = {}
    header = {"Authorization": "Bearer " + token}

    response = requests.get(
        'https://api.github.com/repos/' + owner + '/' + repo_name + '/pulls' +
        '?state=all&sort=updated&direction=desc&since=' + starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"), headers=header)
    if response.status_code == 200:
        for pull in response.json():
            urls = list()
            urls.append('https://api.github.com/repos/' + owner + '/' + repo_name + '/pulls/' +
                        str(pull["number"]) + '/reviews?state=all&sort=created&direction=asc')
            for key, url in pull["_links"].items():
                # or key == "commits"
                if key == "comments" or key == "review_comments":
                    urls.append(url["href"] + '?state=all&sort=created&direction=asc')
            buffer = dict()
            for url in urls:
                response = requests.get(url, headers=header)
                if response.status_code == 200:
                    buffer = buffer | reformat_response(response.json())
                else:
                    print(response.status_code)
            buffer = dict(sorted(buffer.items()))
            if communication_happened(buffer, pull["user"]["id"]):
                update_communications(buffer, all_users, starting_date, pull["user"])
    else:
        print(response.status_code)

    response = requests.get(
        'https://api.github.com/repos/' + owner + '/' + repo_name + '/issues' +
        '?state=all&sort=updated&direction=desc&since=' + starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"), headers=header)
    if response.status_code == 200:
        for issue in response.json():
            response = requests.get(issue["comments_url"] + '?state=all&sort=created&direction=asc', headers=header)
            if response.status_code == 200:
                comments = reformat_response(response.json())
                comments = dict(sorted(comments.items()))
                if communication_happened(comments, issue["user"]["id"]):
                    update_communications(comments, all_users, starting_date, issue["user"])
            else:
                print(response.status_code)
    else:
        print(response.status_code)

    for key in all_users:
        all_users[key].communications = dict(sorted(all_users[key].communications.items(), reverse=True))
    return all_users


def reformat_response(response: dict):
    buffer = dict()
    for item in response:
        if "created_at" in item:
            buffer[datetime.strptime(item["created_at"], "%Y-%m-%dT%H:%M:%SZ")] = item['user']
        elif "submitted_at" in item:
            buffer[datetime.strptime(item["submitted_at"], "%Y-%m-%dT%H:%M:%SZ")] = item['user']
        elif "commit" in item:
            buffer[datetime.strptime(item["commit"]["committer"]["date"], "%Y-%m-%dT%H:%M:%SZ")] = item['author']
    return buffer


def communication_happened(response: dict, id_creator: str):
    if len(response) > 0:
        for date, author in response.items():
            if author["id"] != id_creator:
                return True
    return False


def update_communications(response: dict, all_users: Dict[int, User], starting_date: datetime, author: dict):
    previous_users_ids: Set[int] = set()
    if author["id"] not in all_users:
        all_users[author["id"]] = User(author["id"], author["login"])
    previous_users_ids.add(author["id"])
    for created_date, sender in response.items():
        if sender["id"] not in all_users:
            all_users[sender["id"]] = User(sender["id"], sender["login"])
        if created_date >= starting_date:
            receivers: Set[User] = set()
            for user_id in previous_users_ids:
                if user_id != sender["id"]:
                    receivers.add(all_users[user_id])
            if len(receivers) > 0:
                if created_date in all_users[sender["id"]].communications:
                    all_users[sender["id"]].communications[created_date] = (
                            all_users[sender["id"]].communications[created_date] | receivers)
                else:
                    all_users[sender["id"]].communications[created_date] = receivers
        previous_users_ids.add(sender["id"])
