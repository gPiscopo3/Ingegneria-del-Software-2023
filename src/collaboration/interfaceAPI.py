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
    out = json.loads(repos.text)
    print(json.dumps(out, indent=1))
