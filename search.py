"""Search the cloned repos as specified in config.json, writes search results
to matches.csv and repos.csv.

Assumes clone_orgs.py has already been run to clone the repos.
"""
import json
import os

from utils import file_url, latest_commit


SETTINGS = json.loads(open("config.json").read())  # read config file


def empty_repo_totals():
    """Return the dict structure used to track repo totals.
    """
    temp = {"folder": "", "*TOTAL*": 0}
    for word in SETTINGS["words"]:
        temp[word] = 0
    return temp


def repo_folder(folder_path):
    """Determine whether a path is the root folder of a cloned repo.
    Returns True if a repo root folder, False otherwise.
    """
    # After removing SETTINGS["folder"], should have a path of the form
    # /orgname/repo ...
    sub_path = folder_path.replace(SETTINGS["folder"], "")
    # Convert Windows backslashes (if any) to forward slashes ...
    sub_path = sub_path.replace("\\", "/")
    # If this sub-path has exactly two separators, it's the root folder
    # of a repo ...
    return sub_path.count("/") == 2


def search_file(filename):
    """Searches a file for the words specified in SETTINGS["words"].
    Case-insensitive search.
    Returns a dict with keys for each of the search words (values are # hits),
    as well as a "*TOTAL*" key that is the total number of matches found.
    """
    hit_counts = {"filename": filename, "*TOTAL*": 0}
    with open(filename, "r", encoding="utf-8", errors="replace") as file_handle:
        file_content = file_handle.read().lower()
    for searchfor in SETTINGS["words"]:
        matches = file_content.count(searchfor.lower())
        hit_counts[searchfor] = matches
        hit_counts["*TOTAL*"] += matches
    return hit_counts


def search_repos():
    """Search for words in locally cloned repos.

    SETTINGS["words"] = list of words to search for.
    SETTINGS["filetypes"] = list of file types to be searched.

    Output files:
    matches.csv - list of files that contain one or more of the words
    repos.csv - list of all repos searched, with total matches for each word
    """

    # Create/open the output CSV files.
    matches_file = open("matches.csv", "w")
    matches_file.write(f"url,{','.join(SETTINGS['words'])},total\n")
    repos_file = open("repos.csv", "w")
    repos_file.write(f"url,{','.join(SETTINGS['words'])},total,branch,last_commit\n")

    # We'll use this dict to aggregate totals for each repo searched.
    repo_totals = empty_repo_totals()

    for root, dirs, files in os.walk(SETTINGS["folder"]):
        if "\\vendor\\" in root:
            continue  # skip vendored code
        if repo_folder(root):
            # We're starting searching a new repo, so write totals for previous
            # repo (if any).
            if repo_totals["folder"]:
                write_repo(repos_file, repo_totals)
            repo_totals = empty_repo_totals()  # initialize new repo totals
            repo_totals["folder"] = root
        for filename in files:
            _, extension = os.path.splitext(filename)
            if extension.lower() in SETTINGS["filetypes"]:
                # this is a file to be searched/analyzed
                fullname = os.path.join(root, filename)
                hits = search_file(fullname)
                if hits["*TOTAL*"] > 0:
                    write_matches(matches_file, hits)
                    # Add this file's hit counts to the repo's totals.
                    for word in SETTINGS["words"]:
                        repo_totals[word] += hits[word]
                    repo_totals["*TOTAL*"] += hits["*TOTAL*"]

        # Remove the folders we're not interested in searching.
        if ".git" in dirs:
            dirs.remove(".git")
        if ".github" in dirs:
            dirs.remove(".github")

    write_repo(repos_file, repo_totals)  # write the final repo's totals

    matches_file.close()
    repos_file.close()


def write_matches(file, data):
    """Write a line to the matches.csv file.
    """
    line = file_url(data["filename"])
    for word in SETTINGS["words"]:
        line += f",{data[word]}"
    file.write(f"{line},{data['*TOTAL*']}\n")


def write_repo(file, data):
    """Write a line to the repos.csv file.
    """
    if data["*TOTAL*"] == 0:
        return  # don't include repos with no matches
    branch, commit_sha = latest_commit(data["folder"])
    line = file_url(data["folder"])
    for word in SETTINGS["words"]:
        line += f",{data[word]}"
    file.write(f"{line},{data['*TOTAL*']},{branch},{commit_sha}\n")


if __name__ == "__main__":
    search_repos()
