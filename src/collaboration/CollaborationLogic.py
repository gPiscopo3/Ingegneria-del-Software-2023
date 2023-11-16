from datetime import datetime
from requests.utils import parse_header_links
from src.model.User import User
from src.model.User import create_user
from src.model.File import File
import requests
from itertools import combinations


GITHUB_TOKEN = "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"
HEADER = {"Authorization": "Bearer " + GITHUB_TOKEN}


def create_association(date_start: str, date_end: str, files):
    result = []  # lista di archi
    for file in files:
        collaborators = set()
        for commit_date, author in file.modifiedBy.items():
            if date_start <= commit_date < date_end:
                collaborators.add(author)
        """if len(collaborators) > 0:
            for user in collaborators:
                print(user.username)
        print("")"""
        if len(collaborators) > 1:
            tutte_le_coppie = list(combinations(collaborators, 2))
            result.append(tutte_le_coppie)
        #result.append((file.getId(), collaborators))

    return list(set(tuple(sorted(coppia)) for coppia in result))


def get_collaborations_since(date: str, owner: str, repo_name: str):
    input_date = datetime.strptime(date, "%d/%m/%Y")
    formatted_date_str = input_date.strftime("%Y-%m-%dT00:00:00Z")

    url = "https://api.github.com/repos/" + owner + "/" + repo_name + "/commits?since=" + formatted_date_str

    results = []

    while url:
        response = requests.get(url, headers=HEADER)
        data = response.json()

        if isinstance(data, list):
            results.extend(data)

        # Controlla se ci sono altre pagine
        url = None
        if 'Link' in response.headers:
            links = requests.utils.parse_header_links(response.headers['Link'])
            for link in links:
                if link['rel'] == 'next':
                    url = link['url']

    commits_sha_hashes = []
    for commit in results:
        commits_sha_hashes.append(commit['sha'])
    print(commits_sha_hashes)

    # Prendo le informazioni dei files dai vari commit che vengono modificati dai vari commits
    used_files = []
    for sha in commits_sha_hashes:
        url = "https://api.github.com/repos/" + owner + "/" + repo_name + "/commits/" + sha
        request = requests.get(url, headers=HEADER)
        out = request.json()
        if out['author'] is not None:
            user = create_user(out['author']['id'], out['author']['login'])
            commit_date = out['commit']['author']['date']
            for f in out['files']:
                sha_file = f['sha']
                file = File(sha_file)
                file.addModify(commit_date, user)
                if file in used_files:
                    for element in used_files:
                        if element.identifier == sha_file:
                            element.addModify(commit_date, user)
                else:
                    used_files.append(file)
        else:
            continue

    for file in used_files:
        print(f"Identifier: {file.identifier}")
        for commit_date, author in file.modifiedBy.items():
            print("ModifiedBy: " + commit_date + " author: " + author.username)
        print("")

    coppie = create_association("2023-11-04T16:38:52Z", "2023-11-14T16:38:52Z", used_files)
    #print(coppie)
    for coppia in coppie:
        tuple = coppia[0]
        print(tuple[0].username)
        print(tuple[1].username)
        print("")