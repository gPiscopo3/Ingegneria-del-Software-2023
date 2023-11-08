class User:
    def __init__(self, username):
        self.username = username
        self.comms = dict()

    def __str__(self):
        return self.username
