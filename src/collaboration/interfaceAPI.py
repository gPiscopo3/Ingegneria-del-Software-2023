import json
import requests
from datetime import datetime

GITHUB_TOKEN = "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"


def get_commits_since(date, owner, repo_name):
    input_date = datetime.strptime(date, "%d/%m/%Y")
    formatted_date_str = input_date.strftime("%Y-%m-%dT00:00:00Z")
    header = {"Authorization": "Bearer " + GITHUB_TOKEN}
    repos = requests.get("https://api.github.com/repos/" + owner + "/" + repo_name + "/commits?since=" +
                         formatted_date_str,
                         headers=header)
    out = repos.json()
    sha_hashes = [commit['sha'] for commit in out]
    return sha_hashes
