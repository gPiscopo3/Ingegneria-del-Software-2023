from CommunicationLogic import *
from datetime import datetime, timedelta


TOKEN = "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"


all_users: Dict[int, User] = get_communications("apache", "commons-io", datetime.now() - timedelta(days=30), TOKEN)

for user_id, user in all_users.items():
    user.print_communications()


def communications_in_time_lapse(start: datetime, end: datetime):
    adjacency_map: Dict[User, Set[User]] = dict()
    for key, sender in all_users.items():
        adjacency_map[sender] = set()
        for date, receivers in sender.communications.items():
            if start <= date <= end:
                adjacency_map[sender].update(receivers)
    return adjacency_map


date1 = datetime(year = 2023, month = 11, day = 1, hour = 10, minute = 0, second = 0)
date2 = datetime(year = 2023, month = 11, day = 15, hour = 16, minute = 0, second = 0)
map = communications_in_time_lapse(date1, date2)
for sender, receivers in map.items():
    print(sender.username + ":")
    for r in receivers:
        print(r.username)
    print('')
