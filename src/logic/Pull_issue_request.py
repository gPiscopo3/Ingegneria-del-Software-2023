from datetime import datetime
import requests
from requests.utils import parse_header_links
from src.logic.APICalls import get_with_ratelimit

import requests

BASE_URL = 'https://api.github.com/repos/'
DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


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
