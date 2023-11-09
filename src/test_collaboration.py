from src.collaboration.interfaceAPI import get_commits_since
from src.collaboration.interfaceAPI import get_collab

if __name__ == "__main__":
    commits = get_commits_since("02/11/2023", "tensorflow", "tensorflow")
    print("Stampa di tutti i commits dal 02/11/2023")
    for commit in commits:
        print(commit.to_string())
    print(len(commits))

    filtered_commits = get_collab("05/11/2023", "08/11/2023", commits)
    print("Stampa del filtro su data")
    for commit in filtered_commits:
        print(commit.to_string())
    print(len(filtered_commits))