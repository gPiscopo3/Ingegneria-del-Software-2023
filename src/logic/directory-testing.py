import os
import pickle

owner = "apache"
repo_name = "commons-io"
filename = owner + "_" + repo_name + ".pkl"
logic_directory = os.getcwd()
src_directory = os.path.dirname(logic_directory)
fqdn = os.path.join(src_directory, filename)
# print(os.path.exists(fqdn))


users = {}
with open(fqdn, 'rb') as fp:
    while 1:
        try:
            u = pickle.load(fp)
            users[u.identifier] = u
        except (EOFError, pickle.UnpicklingError):
            break
for ident, us in users.items():
    print(ident, us)