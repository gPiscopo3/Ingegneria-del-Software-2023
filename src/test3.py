import datetime
import json

import requests
from requests.utils import parse_header_links

from src.logic.Pull_issue_request import pulls_json

TOKEN = ""

pulls = pulls_json("tensorflow", "tensorflow", datetime.datetime(2023, 12, 3), TOKEN)

# for pull in pulls:
#     print(pull)
print(len(pulls))
#print(requests.utils.parse_header_links(pulls.headers['Link']))

# dt = datetime.datetime(2023, 12, 6)
# print(dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
