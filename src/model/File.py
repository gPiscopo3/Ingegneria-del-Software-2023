from datetime import datetime
from src.model.User import User


class File:
    def __init__(self, identifier):
        self.identifier = identifier
        self.modifiedBy = {}

    def getId(self):
        return self.identifier

    def getModifiedBy(self):
        return self.modifiedBy

    def addModify(self, date, author):
        self.modifiedBy[date] = author

    def to_string(self):
        return "File: [identifier= " + self.identifier + ", ModifiedBy={" + ";".join([f"{chiave}: {valore}" for chiave,
                    valore in self.modifiedBy.items()]) + "}]"

    def __eq__(self, other):
        if isinstance(other, File):
            return self.identifier == other.identifier
        return False

    def __hash__(self):
        return hash((self.identifier, self.modifiedBy))
