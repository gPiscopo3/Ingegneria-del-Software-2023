from typing import List
from CommunicationLogic import *

# all_users = get_communications("apache", "commons-io", "pulls")
all_users = get_communications("fullmoonlullaby", "test", "issues")
for key in all_users:
    print("Sender: " + all_users[key].username)
    if len(all_users[key].communications) > 0:
        for key2 in all_users[key].communications:
            print(key2)
            receivers: List[User] = all_users[key].communications[key2].receivers
            for r in receivers:
                print(r.username)
    print("")
