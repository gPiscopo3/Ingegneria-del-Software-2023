from typing import List
from CommunicationLogic import *

# all_users = get_issues("apache", "commons-io")
all_users = get_issues("fullmoonlullaby", "test")
for key in all_users:
    print("Sender: " + all_users[key].username)
    if len(all_users[key].comms) > 0:
        for key2 in all_users[key].comms:
            print(key2)
            receivers: List[User] = all_users[key].comms[key2].receivers
            for r in receivers:
                print(r.username)
    print("")
