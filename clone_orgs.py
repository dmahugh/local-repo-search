"""Clone all repos for specified org(s).
Note that we don't clone private repos or forked repos.
"""
import datetime
import json
import os
from timeit import default_timer

from git import Repo  # pip install gitpython

from utils import dicts2json, folder_del, folder_size, github_allpages

# Configuration settings are stored in config.json.
SETTINGS = json.loads(open("config.json").read())


def non_empty_folder(folder):
    """Check whether a folder exists and is not empty.
    Returns False if folder does not exist, or exists and is empty.
    """
    if not os.path.exists(folder):
        return False
    if not os.path.isdir(folder):
        return False
    if not os.listdir(folder):
        return False
    return True


def org_clone(org):
    """Clone all public non-forked repos from the specified org.

    Repos are cloned to subfolders under the 'folder' setting in config.json.
    """
    # optional list of org/repos to be skipped ...
    if os.path.isfile("skiplist.txt"):
        skiplist = open("skiplist.txt").read().lower().splitlines()
    else:
        skiplist = []

    print("Org".ljust(21) + "Repo".ljust(61) + "KB estimate  KB actual  seconds KB/sec")
    print(20 * "-" + " " + 60 * "-" + " " + "----------- ----------- ------- -------")
    # if log file doesn't exist, create it
    logfile = os.path.join(SETTINGS["folder"], "logfile.csv")
    if not os.path.isfile(logfile):
        open(logfile, "w").write(
            "datetime,org,repo,KB-estimate,KB-actual,seconds,KB/second\n"
        )

    org_folder = os.path.join(SETTINGS["folder"], org)
    if SETTINGS["overwrite"]:
        folder_del(org_folder)  # delete existing org data
        os.makedirs(org_folder)  # create empty org folder
    else:
        # In non-overwrite mode, only create org folder if it doesn't exist.
        if not os.path.exists(org_folder):
            os.makedirs(org_folder)

    tot_estimate = 0  # total estimated repo size (from GitHub API)
    tot_actual = 0  # total actual size on disk
    tot_seconds = 0  # total elapsed time

    for repo, size_api in repolist(org):

        if f"{org}/{repo}".lower() in skiplist:
            continue  # repos in skiplist are not cloned

        start = default_timer()
        folder = os.path.join(org_folder, repo)

        if not SETTINGS["overwrite"]:
            # Don't clone this repo if target folder exists and is non-empty.
            if non_empty_folder(folder):
                continue

        print(f"{org:20} {repo:60}   ", end="")

        Repo.clone_from("https://github.com/" + org + "/" + repo + ".git", folder)

        size_actual = folder_size(folder) / 1024
        elapsed = default_timer() - start

        tot_estimate += size_api
        tot_actual += size_actual
        tot_seconds += elapsed

        print(
            f"{size_api:9,.0f}   {size_actual:9,.0f} {elapsed:7.2f} {size_actual/elapsed:7.0f}"
        )

        timestamp = str(datetime.datetime.now())[:19]
        open(logfile, "a").write(
            ",".join(
                [
                    timestamp,
                    org,
                    repo,
                    str(round(size_api)),
                    str(round(size_actual)),
                    str(round(elapsed, 2)),
                    str(round(size_actual / elapsed)),
                ]
            )
            + "\n"
        )

    avg_kb_per_second = 0 if tot_seconds == 0 else tot_actual / tot_seconds
    print(
        "TOTALS:".rjust(84) + f"{tot_estimate:9,.0f}   {tot_actual:9,.0f} "
        f"{tot_seconds:7.2f} {avg_kb_per_second:7.0f}\n"
    )


def repolist(orgname, refresh=True):
    """Return list of repos for a GitHub organization.

    If refresh=False, we use the cached data in /data/repos{orgname}.json and
    don't retrieve the repo data from GitHub API.

    Returns tuples of (reponame, size). Note that this is the size returned
    by the GitHub API, which is typically 2-3X less than actual size.

    We ignore private repos and forks.
    """
    filename = os.path.join(SETTINGS["folder"], orgname.lower()) + "/repodata.json"
    if not refresh and os.path.isfile(filename):
        repodata = json.loads(open(filename, "r").read())  # read cached data
    else:
        endpoint = "/orgs/" + orgname.lower() + "/repos?per_page=100"
        repodata = github_allpages(endpoint=endpoint)
        dicts2json(repodata, filename)
        print(
            f"\r{orgname} - {len(repodata)} total public non-forked repos found"
            + 60 * " "
        )

    return sorted(
        [
            (repo["name"].lower(), repo["size"])
            for repo in repodata
            if not repo["private"] and not repo["fork"]
        ]
    )


if __name__ == "__main__":
    # if cache folder doesn't exist, create it
    if not os.path.isdir(SETTINGS["folder"]):
        os.mkdir(SETTINGS["folder"])

    # refresh the cache
    for ORG in SETTINGS["organizations"]:
        org_clone(ORG)
