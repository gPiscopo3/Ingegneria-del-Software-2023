from logic import DataManagement, APICalls
from datetime import datetime, timedelta
import json


TOKEN = "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"


repos = APICalls.get_repositories_since("Ingegneria del software", "gPiscopo3", datetime.today() - timedelta(days=30), TOKEN)
for repo in repos:
    print(json.dumps(repo, indent=1))

"""
users = DataManagement.get_communications_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=30), TOKEN)

for user in users.values():
    user.print_communications()


files = DataManagement.get_collaborations_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=7), TOKEN)

for file in files.values():
    file.print_edits()
"""
