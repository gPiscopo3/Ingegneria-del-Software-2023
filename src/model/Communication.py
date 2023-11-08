class Communication:
    def __init__(self, sender, date, tipo):
        self.sender = sender
        self.date = date
        self.tipo = tipo
        self.receivers = list()
