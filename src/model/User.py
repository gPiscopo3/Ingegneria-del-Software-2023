from datetime import datetime
from typing import Dict, Set


class User:
    def __init__(self, identifier, username):
        self.username: str = username
        self.identifier: str = identifier
        self.communications: Dict[datetime, Set[User]] = {}

    def sort_communications(self):
        self.communications = dict(sorted(self.communications.items(), reverse=True))

    def update_communication(self, date: datetime, receivers: set):
        if date not in self.communications:
            self.communications[date] = set()
        self.communications[date] = self.communications[date] | receivers

    def print_communications(self):
        print("Sender: " + self.username)
        print(" ")
        for date, receivers in self.communications.items():
            print(date)
            for r in receivers:
                print(r.username)
            print(" ")
        print("-------")

    def __str__(self):
        return "User: [identifier= " + str(self.identifier) + ", username= " + self.username + "]"
