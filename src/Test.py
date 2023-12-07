from logic import DataManagement
from datetime import datetime
from datetime import timedelta

'''
TOKEN = "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"

users = DataManagement.get_communications_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=30), TOKEN)

for user in users.values():
    user.print_communications()


files = DataManagement.get_collaborations_since("fullmoonlullaby", "test", datetime.today() -
                                                timedelta(days=14), TOKEN)

for file in files.values():
    file.print_edits()
'''

from logic import DataManagement

import datetime

from src.logic.Filters import collaborations_in_range

TOKEN = "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"

files = DataManagement.get_collaborations_since("apache", "commons-io",
                                                datetime.datetime(2023, 11, 18), TOKEN)

edges = collaborations_in_range(datetime.datetime(2023, 11, 18),
                                datetime.datetime(2023, 12, 6), files)

for edge in edges:
    for user in edge:
        print(user[0].username, user[1].username)
