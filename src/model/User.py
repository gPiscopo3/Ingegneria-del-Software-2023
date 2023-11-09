from datetime import datetime
from typing import Dict
from model.Communication import Communication


class User:
    def __init__(self, username):
        self.username: str = username
        self.communications: Dict[datetime, Communication] = {}
