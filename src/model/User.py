class User:
    def __init__(self, identifier, username):
        self.identifier = identifier
        self.username = username

    def to_string(self):
        return "User: [identifier= " + str(self.identifier) + ", username= " + self.username + "]"


def create_user(identifier, username):
    if identifier is not None and username is not None:
        return User(identifier, username)
    else:
        return User("void", "void")
