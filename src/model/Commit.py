class Commit:
    def __init__(self, sha, date, author, files):
        self.sha = sha              # String
        self.date = date            # Datetime
        self.author = author        # String
        self.files = files          # String List
