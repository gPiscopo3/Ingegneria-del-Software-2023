import datetime
import os
from src.logic.DataManagement import get_communications_since
from src.logic.Filters import communications_in_range
import pickle

TOKEN = "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"
header = {"Authorization": "Bearer " + TOKEN}
dt = datetime.datetime(2023, 12, 13)

#print(os.path.abspath(__file__))

# owner = "tensorflow"
# repo_name = "tensorflow"
# filename = owner + "_" + repo_name + ".pkl"
# print(filename)

# with open(filename, 'rb') as fp:
#     u = pickle.load(fp)
#
# print(u.username)

# file_name = "apache_commons-io.pkl"  # file to be searched
# cur_dir = os.getcwd()
# fqdn = os.path.join(cur_dir, file_name)
# parent = os.path.dirname(fqdn)
# print(parent)
# print(os.path.exists(fqdn))

# print(os.path.exists("C:\Users\pc\OneDrive\Desktop\Ingegneria-del-Software-2023\src\apache_commons-io.pkl"))

comm_locali = get_communications_since("tensorflow", "tensorflow", dt, TOKEN)
for ident, us in comm_locali.items():
    print(ident, us)
# print(len(list(comm_locali.values())))


# adj = communications_in_range(datetime.datetime(2023, 12, 1),
#                               datetime.datetime(2023, 12, 15), comm_locali)
# print(adj)

# with open('apache_commons-io.pkl', 'wb') as fp:
#     for user in comm_locali.values():
#         pickle.dump(user, fp)

# users = {}
# with open(filename, 'rb') as fp:
#     i = 1
#     while 1:
#         try:
#             u = pickle.load(fp)
#             users[u.identifier] = u
#         except (EOFError, pickle.UnpicklingError):
#             break
#
#
# for ident, us in users.items():
#     print(ident, us)

# for u in users:
#     print(u.username)
#     print("ha comunicato ")
#     for date, set_utenti in u.communications.items():
#         print("in data ", date)
#         for receiver in set_utenti:
#             print(receiver.username)
#     print()
