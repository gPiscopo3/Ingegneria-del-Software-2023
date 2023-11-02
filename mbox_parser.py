import os
import mailbox
import sys
import pprint


# Dichiarazione delle classi
class Email:
    def __init__(self, sender, inReplyTo, messageID):
        self.sender = sender
        self.inReplyTo = inReplyTo
        self.messageID = messageID

    def print_elements(self):
        print("[sender: " + self.sender + "; In-Reply-To: " + self.inReplyTo + "; Message-ID: " + self.messageID + "]")


class Edge:
    def __init__(self, sender, receiver):
        self.sender = sender
        self.receiver = receiver

    def print_elements(self):
        print("[sender: " + self.sender + "; receiver: " + self.receiver + "]")


# Inizio del codice
print("Reading emails:")

# mbox_file = "/home/giuseppe/PycharmProjects/IngegneriaDelSoftware2023/dev_commons_apache_org.mbox"
mbox_file = "/home/giuseppe/PycharmProjects/IngegneriaDelSoftware2023/tdwg-lit.mbox"

print("Processing " + mbox_file)
mbox = mailbox.mbox(mbox_file)

email_list = []
edges = []

for key in mbox.iterkeys():

    try:
        message = mbox[key]
    except mbox.errors.MessageParseError:
        continue  # The message is malformed. Just leave it.

    email = Email(message['From'], str(message['In-Reply-To']), message['Message-ID'])
    email_list.append(email)
    # print("Done.")
    # print("")

for email in email_list:
    email.print_elements()


for first in email_list:
    for second in email_list:
        if first.inReplyTo == second.messageID:
            edge = Edge(first.sender, second.sender)
            edges.append(edge)
        else:
            continue

print("")
for edge in edges:
    edge.print_elements()

print("Numero email: " + str(len(email_list)))
print("Numero archi: " + str(len(edges)))
