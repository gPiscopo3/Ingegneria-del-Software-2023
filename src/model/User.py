from datetime import datetime
from typing import Dict
from model.Communication import Communication


class User:
    def __init__(self, username):
        self.username = username
        self.comms: Dict[datetime, Communication] = {}

    def __str__(self):
        return self.username
