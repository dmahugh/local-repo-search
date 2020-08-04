"""
Filters a CSV file to eliminate rows that meet these two criteria:

- repo is in the googleapis org on Github
- repo is not included in repos.json at this URL:
  https://raw.githubusercontent.com/googleapis/sloth/master/repos.json

The header row of the input file and all rows not meeting the above criteria are
written to the output file.
"""
import csv
import sys

import requests


def main(input_csv, output_csv):
    """main function

    args:
        infile:  input CSV filename
        outfile: output CSV filename (will be overwritten if exists)
    """

    # Load repos.json into memory, as a list of the (lower-case) names of the repos
    # from the googleapis org that we want to include in the output.
    resp = requests.get(
        "https://raw.githubusercontent.com/googleapis/sloth/master/repos.json"
    )
    repo_data = resp.json()["repos"]
    repos = [
        repo["repo"].lower().split("/")[1]
        for repo in repo_data
        if repo["repo"].split("/")[0].lower() == "googleapis"
    ]

    # open input/output CSV files
    in_handle = open(input_csv, "r")
    out_handle = open(output_csv, "w", newline="\n")
    infile = csv.reader(in_handle, dialect="excel")
    outfile = csv.writer(out_handle, dialect="excel")

    for row in infile:
        if row[0] == "url":
            # header row
            outfile.writerow(row)
            continue
        url_parts = row[0].split("/")
        org = url_parts[3].lower()
        repo = url_parts[4].lower()
        if org == "googleapis":
            if repo in repos:
                outfile.writerow(row)
        else:
            # Copy all repos not in googleapis org.
            outfile.writerow(row)

    in_handle.close()
    out_handle.close()


if __name__ == "__main__":
    if len(sys.argv) != 3 or not sys.argv[1] or not sys.argv[2]:
        print("INVALID SYNTAX")
        print("Usage: python repo_filter.py <input_file.csv> <output_file.csv>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
