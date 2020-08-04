"""miscellaneous utilities/helper functions
"""
import contextlib
import json
import os
import shutil
import time

import requests

SETTINGS = json.loads(open("config.json").read())  # read config file


def dicts2json(source=None, filename=None):
    """Write list of dictionaries to a JSON file.

    source   = the list of dictionaries
    filename = the filename (will be over-written if it already exists)
    """
    if not source or not filename:
        return  # nothing to do
    with open(filename, "w") as fhandle:
        fhandle.write(json.dumps(source, indent=4, sort_keys=True))


def file_url(filename):
    """Convert a local filename to the file's URL on GitHub."""
    gh_path = filename.replace("\\", "/")[15:]  # org/repo/path_to_file
    url = (
        "https://github.com/"
        + "/".join(gh_path.split("/")[:2])
        + "/blob/master/"
        + "/".join(gh_path.split("/")[2:])
    )
    if url.endswith("/blob/master/"):
        # This is a hack, but since we use this function for the repo URL also,
        # remove /blob/master/ if the URL ends with that.
        url = url[:-13]
    return url


def folder_del(path):
    """Delete a folder and its contents."""
    if not os.path.isdir(path):
        return
    with contextlib.suppress(OSError):
        shutil.rmtree(path, onerror=folder_del_onerror)


def folder_del_onerror(action, name, exc): # pylint: disable=W0613
    """Error handler for folder_del(), to delete read-only files."""
    os.chmod(name, 128)  # clear read-only attribute
    time.sleep(0.1)  # this seems to eliminate intermittent PermissionError
    os.remove(name)


def folder_size(path):
    """Return total size of a folder, including contents/subfolders."""
    if not os.path.isdir(path):
        return 0
    total_bytes = 0
    for entry in os.scandir(path):
        if entry.is_dir(follow_symlinks=False):
            total_bytes += folder_size(entry.path)
        else:
            total_bytes += entry.stat(follow_symlinks=False).st_size
    return total_bytes


def github_allpages(endpoint=None, auth=None, headers=None, state=None, session=None):
    """Retrieve a paginated data set from GitHub V3 REST API.

    endpoint = HTTP endpoint for GitHub API call
    headers  = HTTP headers to be included with API call

    Returns the data as a list of dictionaries. Pagination is handled,
    so the complete data set is returned.
    """

    headers = {} if not headers else headers

    payload = []  # the full data set (all fields, all pages)
    page_endpoint = endpoint  # endpoint of each page in the loop below

    while True:
        response = github_rest_api(
            endpoint=page_endpoint,
            auth=auth,
            headers=headers,
            state=state,
            session=session,
        )
        if (state and state.verbose) or response.status_code != 200:
            # note that status code is always displayed if not 200/OK
            print(">>> endpoint: {0}".format(endpoint))
            print(
                "      Status: {0}, {1} bytes returned".format(
                    response, len(response.text)
                )
            )
        if response.ok:
            thispage = json.loads(response.text)
            payload.extend(thispage)

        pagelinks = github_pagination(response)
        page_endpoint = pagelinks["nextURL"]
        if not page_endpoint:
            break  # no nextURL, so that was the last page of data

    return payload


def github_pagination(link_header):
    """Parse values from the 'link' HTTP header returned by GitHub API.

    1st parameter = either the 'link' HTTP header string, or the
                    response object returned by requests library

    Returns a dictionary with entries for the URLs and page numbers parsed
    from the link string: firstURL, firstpage, prevURL, prevpage, nextURL,
    nextpage, lastURL, lastpage.
    """
    retval = {
        "firstpage": 0,
        "firstURL": None,
        "prevpage": 0,
        "prevURL": None,
        "nextpage": 0,
        "nextURL": None,
        "lastpage": 0,
        "lastURL": None,
    }

    if isinstance(link_header, str):
        link_string = link_header
    else:
        # link_header is a Requests response object
        try:
            link_string = link_header.headers["Link"]
        except KeyError:
            return retval  # no Link HTTP header found, nothing to parse

    links = link_string.split(",")
    for link in links:
        # link format = '<url>; rel="type"'
        linktype = link.split(";")[-1].split("=")[-1].strip()[1:-1]
        url = link.split(";")[0].strip()[1:-1]
        pageno = url.split("?")[-1].split("=")[-1].strip()

        retval[linktype + "page"] = pageno
        retval[linktype + "URL"] = url

    return retval


def github_rest_api(
        *, endpoint=None, auth=None, headers=None, state=None, session=None
    ):
    """Do a GET from the GitHub V3 REST API.

    endpoint = the HTTP endpoint to call; if endpoint starts with / (for
               example, '/orgs/microsoft'), it will be appended to
               https://api.github.com
    auth     = optional authentication tuple - (username, pat)
               If not specified, values are read from username/PAT settings in
               local config.json file
    headers  = optional dictionary of HTTP headers to pass
    state    = optional state object, where settings such as the session object
               are stored. If provided, must have properties as used below.
    session  = optional Requests session object reference. If not provided,
               state.requests_session is the default session object. Use
               the session argument to override that default and use a
               different session. Use of a session object improves performance.

    Returns the response object.

    Sends the Accept header to use version V3 of the GitHub API. This can
    be explicitly overridden by passing a different Accept header if desired.
    """
    print(f"\rGitHub API called: {endpoint}", end="")

    if not endpoint:
        print("ERROR: github_api() called with no endpoint")
        return None

    # set auth to default if needed
    if not auth:
        settings = json.loads(open("config.json").read())  # read config file
        auth = (settings["username"], settings["PAT"])

    # add the V3 Accept header to the dictionary
    headers = {} if not headers else headers
    headers_dict = {**{"Accept": "application/vnd.github.v3+json"}, **headers}

    # make the API call
    if session:
        sess = session  # explictly passed Requests session
    elif state:
        if state.requests_session:
            sess = state.requests_session  # Requests session on the state objet
        else:
            sess = requests.session()  # create a new Requests session
            state.requests_session = sess  # save it in the state object
    else:
        # if no state or session specified, create a temporary Requests
        # session to use below. Note it's not saved/re-used in this scenario
        # so performance won't be optimized.
        sess = requests.session()

    sess.auth = auth
    full_endpoint = (
        "https://api.github.com" + endpoint if endpoint[0] == "/" else endpoint
    )
    response = sess.get(full_endpoint, headers=headers_dict)

    if state and state.verbose:
        print("    Endpoint: " + endpoint)

    if state:
        # update rate-limit settings
        try:
            state.last_ratelimit = int(response.headers["X-RateLimit-Limit"])
            state.last_remaining = int(response.headers["X-RateLimit-Remaining"])
        except KeyError:
            # This is the strange and rare case (which we've encountered) where
            # an API call that normally returns the rate-limit headers doesn't
            # return them. Since these values are only used for monitoring, we
            # use nonsensical values here that will show it happened, but won't
            # crash a long-running process.
            state.last_ratelimit = 999999
            state.last_remaining = 999999

        if state.verbose:
            # display rate-limite status
            username = auth[0] if auth else "(non-authenticated)"
            used = state.last_ratelimit - state.last_remaining
            print(
                "  Rate Limit: {0} available, {1} used, {2} total for {3}".format(
                    state.last_remaining, used, state.last_ratelimit, username
                )
            )

    return response


def latest_commit(folder):
    """Get latest commit for a Git repo.
    Takes the folder of a local git repo, and returns a tuple of the
    default branch and SHA of the latest commit in that branch.
    """
    git_heads_folder = os.path.join(folder, ".git\\refs\\heads")
    try:
        heads = next(os.walk(git_heads_folder))[2]
    except StopIteration:
        heads = None
    if heads:
        default_branch = heads[0]
        with open(os.path.join(git_heads_folder, default_branch)) as fhandle:
            commit_sha = fhandle.read().strip()
    else:
        default_branch = ""
        commit_sha = ""

    return (default_branch, commit_sha)


if __name__ == "__main__":
    for org in SETTINGS["organizations"]:
        org_folder = os.path.join(SETTINGS["folder"], org)
        repos = next(os.walk(org_folder))[1]
        for repo in repos:
            repo_folder = os.path.join(org_folder, repo)
            branch, sha = latest_commit(repo_folder)
            print(f"{branch} {sha} {repo_folder}")
