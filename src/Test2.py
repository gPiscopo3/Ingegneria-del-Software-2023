from logic import DataManagement
from src.logic.APICalls import get_with_ratelimit

import datetime

from src.logic.Filters import collaborations_in_range

# TOKEN = ""
#
# files = DataManagement.get_collaborations_since("apache", "commons-io",
#                                                 datetime.datetime(2023, 11, 25), TOKEN)
#
# edges = collaborations_in_range(datetime.datetime(2023, 11, 25),
#                                 datetime.datetime(2023, 12, 6), files)
#
# for edge in edges:
#     for user in edge:
#         print(user[0].username, user[1].username)


response = get_with_ratelimit('https://api.github.com/repos/gPiscopo3/Ingegneria-del-Software-2023/issues',
                              {})
print(response.json())