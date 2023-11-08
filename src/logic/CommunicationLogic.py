from src.model.User import User
from src.model.Communication import Communication
import requests as r
import datetime


def getissues():
    allusers = dict()
    startingdate = (datetime.datetime.now() - datetime.timedelta(days=14))
    response = r.get(
        'https://api.github.com/repos/apache/commons-io/issues?state=all&sort=updated&direction=desc'
        '&since=' + startingdate.strftime("%Y-%m-%dT%H:%M:%SZ"))
    if response.status_code == 200:
        for i in response.json():
            issue = i["number"]
            response = r.get(
                'https://api.github.com/repos/apache/commons-io/issues/' + str(issue) + '/comments'
                '?state=all&sort=created&direction=asc&since=' + startingdate.strftime("%Y-%m-%dT%H:%M:%SZ"))
            if response.status_code == 200:
                users = set()
                for c in response.json():
                    createddate = datetime.datetime.strptime(c["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                    if createddate >= startingdate:
                        username = c["user"]["login"]
                        if allusers.get(username) is None:
                            allusers[username] = User(username)
                        user = allusers[username]
                        if len(users) > 0:
                            communication = Communication(user, createddate, 'issue')
                            communication.receivers = users
                            if user in users:
                                communication.receivers.remove(user)
                            user.comms[createddate] = communication
                        users.add(user)
            else:
                print(response.status_code)
    else:
        print(response.status_code)
    for key in allusers:
        print("Sender: " + allusers[key].username)
        if len(allusers[key].comms) > 0:
            for key2 in allusers[key].comms:
                print(key2)
        print("")
