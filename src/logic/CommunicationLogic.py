from src.model.User import User
from src.model.Communication import Communication
from typing import Dict, Set
from datetime import datetime
import requests


TOKEN = "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"


def get_communications(owner: str, repo_name: str, starting_date: datetime, token: str):
    all_users: Dict[int, User] = {}
    header = {"Authorization": "Bearer " + token}

    response = requests.get(
        'https://api.github.com/repos/' + owner + '/' + repo_name + '/issues' +
        '?state=all&sort=updated&direction=desc&since=' + starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"), headers=header)
    if response.status_code == 200:
        for issue in response.json():
            response = requests.get(
                'https://api.github.com/repos/' + owner + '/' + repo_name + '/issues/' +
                str(issue["number"]) + '/comments?state=all&sort=created&direction=asc', headers=header)
            if response.status_code == 200:
                comments = reformat_response(response.json(), "created_at")
                comments = dict(sorted(comments.items()))
                if communication_happened(comments, issue["user"]["id"]):
                    update_communications(comments, all_users, starting_date, "issue", issue["user"])
            else:
                print(response.status_code)
    else:
        print(response.status_code)

    """
    response = requests.get(
        'https://api.github.com/repos/' + owner + '/' + repo_name + '/pulls' +
        '?state=all&sort=updated&direction=desc&since=' + starting_date.strftime("%Y-%m-%dT%H:%M:%SZ"), headers=header)
    if response.status_code == 200:
        for pull in response.json():
            response_comments = requests.get(
                'https://api.github.com/repos/' + owner + '/' + repo_name + '/pulls/' +
                str(pull["number"]) + '/comments?state=all&sort=created&direction=asc', headers=header)
            response_reviews = requests.get(
                'https://api.github.com/repos/' + owner + '/' + repo_name + '/pulls/' +
                str(pull["number"]) + '/reviews?state=all&sort=created&direction=asc', headers=header)
            if response_comments.status_code == 200 and response_reviews.status_code == 200:
                comments = reformat_response(response_comments.json(), "created_at")
                reviews = reformat_response(response_reviews.json(), "submitted_at")
                buffer = comments | reviews
                buffer = dict(sorted(buffer.items()))
                if communication_happened(buffer, pull["user"]["id"]):
                    update_communications(buffer, all_users, starting_date, "pull", pull["user"])
            else:
                print(str(response_comments.status_code) + ' ' + str(response_reviews.status_code))
    else:
        print(response.status_code)
    """

    for key in all_users:
        all_users[key].communications = dict(sorted(all_users[key].communications.items(), reverse=True))
    return all_users


def reformat_response(response: dict, date_key: str):
    buffer = dict()
    for element in response:
        buffer[datetime.strptime(element[date_key], "%Y-%m-%dT%H:%M:%SZ")] = element['user']
    return buffer


def communication_happened(response: dict, id_creator: str):
    if len(response) > 0:
        for date, author in response.items():
            if author["id"] != id_creator:
                return True
    return False


def update_communications(response: dict, all_users: Dict[int, User], starting_date: datetime, comm_type: str,
                          creator: dict):
    previous_users_ids: Set[int] = set()
    if all_users.get(creator["id"]) is None:
        all_users[creator["id"]] = User(creator["id"], creator["login"])
    previous_users_ids.add(creator["id"])
    for created_date, author in response.items():
        if all_users.get(author["id"]) is None:
            all_users[author["id"]] = User(author["id"], author["login"])
        if created_date >= starting_date:
            communication = Communication(all_users[author["id"]], created_date, comm_type)
            for user_id in previous_users_ids:
                if user_id != author["id"]:
                    communication.receivers.append(all_users[user_id])
            if len(communication.receivers) > 0:
                all_users[author["id"]].communications[created_date] = communication
        previous_users_ids.add(author["id"])
