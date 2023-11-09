class Commit:
    def __init__(self, sha, date, author, files):
        self.sha = sha              # String
        self.date = date            # Datetime
        self.author = author        # String
        self.files = files          # String List

    def to_string(self):
        return ("Commit[sha= " + self.sha + ", date= " + self.date + ", author= " + self.author + ", files: " +
                str(self.files) + "]")

