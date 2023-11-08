from src.collaboration.interfaceAPI import get_commits_since

if __name__ == "__main__":
    sha_hashes = get_commits_since("10/10/2023", "tensorflow", "tensorflow")
    print("SHA dei commits della richiesta:")
    for sha in sha_hashes:
        print(sha)
