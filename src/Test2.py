from logic import DataManagement

import datetime

from src.logic.Filters import collaborations_in_range

TOKEN = ""

files = DataManagement.get_collaborations_since("apache", "commons-io",
                                                datetime.datetime(2023, 11, 25), TOKEN)

edges = collaborations_in_range(datetime.datetime(2023, 11, 25),
                                datetime.datetime(2023, 12, 6), files)

for edge in edges:
    for user in edge:
        print(user[0].username, user[1].username)
