import json
import requests
from requests.utils import parse_header_links
from datetime import datetime
from src.model.Commit import Commit

GITHUB_TOKEN = "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"
HEADER = {"Authorization": "Bearer " + GITHUB_TOKEN}


def get_commits_since(date, owner, repo_name):
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

    # print(results)

    commits = []
    for commit in results:
        sha = commit['sha']
        author = commit['commit']['author']['name']
        date = commit['commit']['author']['date']
        files = get_files(sha, owner, repo_name)
        c = Commit(sha, date, author, files)
        commits.append(c)
    return commits


def get_files(sha, owner, repo_name):
    request = requests.get("https://api.github.com/repos/" + owner + "/" + repo_name + "/commits/" + sha,
                           headers=HEADER)
    files = []
    out = request.json()
    for file in out['files']:
        files.append(file['sha'])

    return files


def get_collab(date_start, date_end, commits):
    input_date_s = datetime.strptime(date_start, "%d/%m/%Y")
    formatted_date_str_s = input_date_s.strftime("%Y-%m-%dT00:00:00Z")
    input_date_e = datetime.strptime(date_end, "%d/%m/%Y")
    formatted_date_str_e = input_date_e.strftime("%Y-%m-%dT00:00:00Z")

    filtered_commits = []
    for commit in commits:
        if formatted_date_str_s < commit.date < formatted_date_str_e:
            filtered_commits.append(commit)

    return filtered_commits
