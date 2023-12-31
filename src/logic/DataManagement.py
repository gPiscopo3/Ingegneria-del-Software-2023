from src.model.File import File
from src.model.User import User
from typing import Dict, Set
from datetime import datetime
from src.logic import APICalls
import os
import pickle


def get_communications_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    all_users: Dict[int, User] = {}  # conterrà ogni utente che ha comunicato con le sue relative comunicazioni

    filename = owner + "_" + repo_name + ".pkl"
    full_path_di_DataManagement = os.path.abspath(__file__)
    src_directory = os.path.dirname(os.path.dirname(full_path_di_DataManagement))
    path_to_search_cache = os.path.join(src_directory, filename)
    if os.path.exists(path_to_search_cache):
        with open(path_to_search_cache, 'rb') as fp:
            while 1:
                try:
                    u = pickle.load(fp)
                    all_users[u.identifier] = u
                except (EOFError, pickle.UnpicklingError):
                    break

    else:
        # pull requests
        results = APICalls.get_pulls_since(owner, repo_name, starting_date, token)
        for pull in results:
            if communication_happened(pull):
                update_communications(pull, all_users, starting_date)

        # issues
        results = APICalls.get_issues_since(owner, repo_name, starting_date, token)
        for issue in results:
            if communication_happened(issue):
                update_communications(issue, all_users, starting_date)

        for key, user in all_users.items():  # ordina per data (discendente) le comunicazioni di ogni utente
            user.sort_communications()
        save_all_user(path_to_search_cache, all_users)

    return all_users  # dictionary {user_id: user}, in ogni user ci sono tutte le sue comunicazioni


def get_collaborations_since(owner: str, repo_name: str, starting_date: datetime, token: str):
    collaborators: Dict[int, User] = {}  # conterrà la lista degli utenti che hanno commitato
    files: Dict[str, File] = {}  # conterrà ogni file presente nei commit e coppie data:autore per ogni modifica

    filename = owner + "_" + repo_name + "_collabs.pkl"
    full_path_di_DataManagement = os.path.abspath(__file__)
    src_directory = os.path.dirname(os.path.dirname(full_path_di_DataManagement))
    path_to_search_cache = os.path.join(src_directory, filename)

    if os.path.exists(path_to_search_cache):
        with open(path_to_search_cache, 'rb') as fp:
            while 1:
                try:
                    f = pickle.load(fp)
                    files[f.identifier] = f
                except (EOFError, pickle.UnpicklingError):
                    break
    else:
        results = APICalls.get_commits_since(owner, repo_name, starting_date, token)
        for commit in results:
            if commit['author'] is not None and "files" in commit:

                if commit['author']['id'] not in collaborators:  # crea l'utente se non è già presente in collaborators
                    collaborators[commit['author']['id']] = User(commit['author']['id'], commit['author']['login'])

                for file in commit['files']:
                    if file['filename'] not in files:  # crea il file se non è già presente in files
                        files[file['filename']] = File(file['filename'])
                    files[file['filename']].add_edit(
                        datetime.strptime(commit['commit']['author']['date'], "%Y-%m-%dT%H:%M:%SZ"),
                        collaborators[commit['author']['id']])

        for sha, file in files.items():  # ordina per data (discendente) le modifiche di ogni file
            file.sort_edits()
        save_all_user(path_to_search_cache, files)

    return files  # dictionary {file_id: file}, in ogni file ci sono tutte le modifiche avvenute


# funzioni "private" delle funzioni di sopra

# controlla se c'è almeno una risposta di uno user diverso dall'autore della pull request/issue
def communication_happened(response: dict):
    if len(response) > 0:
        id_creator = next(iter(response.values()))['id']
        for date, author in response.items():
            if author["id"] != id_creator:
                return True
    return False


# itera le risposte ordinate per data salvando le comunicazioni generate da ogni risposta
def update_communications(response: dict, all_users: Dict[int, User], starting_date: datetime):
    previous_users_ids: Set[int] = set()  # buffer in cui sono salvati gli autori delle risposte precedenti
    for created_date, sender in response.items():

        if sender["id"] not in all_users:  # crea l'utente se non è già presente in all_users
            all_users[sender["id"]] = User(sender["id"], sender["login"])

        if created_date >= starting_date:  # controlla se risposta è inviata nell'intervallo temporale di interesse

            receivers: Set[User] = set()  # receivers = tutti gli autori delle risposte precedenti*
            for user_id in previous_users_ids:
                if user_id != sender["id"]:  # *tranne se stesso
                    receivers.add(all_users[user_id])

            if len(receivers) > 0:  # se l'utente ha comunicato con almeno un altro utente, aggiungo comunicazioni
                all_users[sender["id"]].update_communication(created_date, receivers)

        previous_users_ids.add(sender["id"])  # aggiunge l'autore della risposta nel buffer


def save_all_user(filename: str, dizionario):
    if not dizionario:
        return
    try:
        with open(filename, 'wb') as fp:
            for elem in dizionario.values():
                pickle.dump(elem, fp)
    except TypeError:
        print("TypeError: None type")
    except OSError:
        print("TypeError: wrong type")
    except AttributeError:
        os.remove(filename)


# def save_all_files(filename: str, dizionario_di_file):
#     with open(filename, 'wb') as fp:
#         for elem in dizionario_di_file.values():
#             pickle.dump(elem, fp)
