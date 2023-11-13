from typing import List
from CommunicationLogic import *
from datetime import datetime, timedelta


TOKEN = "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"


all_users = get_communications("fullmoonlullaby", "test", datetime.now() - timedelta(days=7), TOKEN)

for key in all_users:
    print("Sender: " + all_users[key].username)
    if len(all_users[key].communications) > 0:
        for key2, value in all_users[key].communications.items():
            print(key2)
            receivers: List[User] = value.receivers
            for r in receivers:
                print(r.username)
    print("")

def communications_in_time_lapse(start: datetime, end: datetime):
    adjacency_map: Dict[User, Set[User]] = dict()
    for key, sender in all_users.items():
        adjacency_map[sender] = set()
        for date, communication in sender.communications.items():
            if start <= date <= end:
                adjacency_map[sender].update(communication.receivers)
    return adjacency_map


date1 = datetime(year = 2023, month = 11, day = 9, hour = 10, minute = 0, second = 0)
date2 = datetime(year = 2023, month = 11, day = 9, hour = 16, minute = 0, second = 0)
map = communications_in_time_lapse(date1, date2)
for sender, receivers in map.items():
    print(sender.username + ":")
    for r in receivers:
        print(r.username)
    print('')
