from datetime import datetime
from typing import Dict, Set


class User:
    def __init__(self, identifier, username):
        self.username: str = username
        self.identifier: str = identifier
        self.communications: Dict[datetime, Set[User]] = {}

    def print_communications(self):
        print("Sender: " + self.username)
        print(" ")
        for date, receivers in self.communications.items():
            print(date)
            for r in receivers:
                print(r.username)
            print(" ")
        print("-------")

    def to_string(self):
        return "User: [identifier= " + str(self.identifier) + ", username= " + self.username + "]"


def create_user(identifier, username):
    if identifier is not None and username is not None:
        return User(identifier, username)
    else:
        return User("void", "void")
