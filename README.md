# local-repo-search
Miscellaneous utilities for cloning and searching repos.

It can be time-consuming to search across a large number of repos with the GitHub
API, so I've written these simple tools to allow for faster search operations by
cloning the repos to local disk. The basic concept is that you use clone_orgs.py
to clone all of the repos from selected GitHub organizations and then you can run
local searches with search.py. Configuration information is in config.json.
