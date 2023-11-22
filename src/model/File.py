from datetime import datetime
from typing import Dict
from src.model.User import User


class File:
    def __init__(self, identifier):
        self.identifier: str = identifier
        self.modifiedBy: Dict[datetime, User] = {}

    def add_edit(self, date, author):
        self.modifiedBy[date] = author

    def sort_edits(self):
        self.modifiedBy = dict(sorted(self.modifiedBy.items(), reverse=True))

    def __str__(self):
        return "File: [identifier= " + self.identifier + ", ModifiedBy={" + ";".join([f"{chiave}: {valore}" for chiave,
                    valore in self.modifiedBy.items()]) + "}]"

    def __eq__(self, other):
        if isinstance(other, File):
            return self.identifier == other.identifier
        return False

    def __hash__(self):
        return hash((self.identifier, self.modifiedBy))
