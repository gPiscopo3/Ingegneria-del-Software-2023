from datetime import datetime
from requests.utils import parse_header_links
from src.model.User import User
from src.model.User import create_user
from src.model.File import File
import requests

GITHUB_TOKEN = "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"
HEADER = {"Authorization": "Bearer " + GITHUB_TOKEN}


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
        print(f"Identifier: {file.identifier}, ModifiedBy: {file.modifiedBy}")
