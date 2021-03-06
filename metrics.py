import requests
import json
import sys
from packaging import version
import semver
from datetime import datetime
from collections import defaultdict
import hashlib
import os

#
# Crates.io
#


# obtain crate info
def get_crate_info(crate: str) -> dict:
    # check if cache exists
    if os.path.exists("cache/" + crate):
        f = open("cache/" + crate, "r")
        return json.load(f)

    r = requests.get("https://crates.io/api/v1/crates/" + crate)
    if r.status_code != 200:
        print("couldn't query crates.io")
        return
    res = r.json()

    # cache result
    w = open("cache/" + crate, "w")
    json.dump(res, w)

    #
    return res


# extract useful information from crates.io response
def extract_from_info(info: dict) -> list:
    # get sorted list of ("semver", "date") tuples
    versions = []
    for v in info["versions"]:
        # there can be some invalid "yank" and "tmp" versions
        try:
            version.Version(v["num"])
        except:
            continue

        versions.append({
            "version": v["num"],
            "date": v["created_at"],
        })

    # sort by version (we could sort by date also)
    versions = sorted(versions, key=lambda x: version.Version(x["version"]))

    return versions


#
# Metrics
#

# get number of versions between two semvers
def get_versions_landed(dep: dict) -> int:
    versions = [d["version"] for d in dep["all_versions"]]
    return versions.index(dep["new_version"]) - versions.index(dep["old_version"])


def get_semver_type_update(dep: dict) -> str:
    return what_kind_of_update(dep["old_version"], dep["new_version"])


def what_kind_of_update(old: str, new: str) -> str:
    old = semver.VersionInfo.parse(old)
    new = semver.VersionInfo.parse(new)

    if old.major != new.major:
        return "MAJOR"
    elif old.minor != new.minor:
        return "MINOR"
    elif old.patch != new.patch:
        return "PATCH"
    elif old.prerelease != new.prerelease:
        return "PRERELEASE"
    elif old.build != new.build:
        return "BUILD"
    print(f"unable to parse version change between {old} and {new}")
    return "UNKNOWN"


def dep_file_to_list(lines: str) -> dict:
    deps = {}
    for line in lines:
        parsed = line.split(" ")
        name = parsed[0]
        versionn = parsed[1]
        registry = parsed[2]

        if registry.strip() != "(registry+https://github.com/rust-lang/crates.io-index)":
            print(f"- not including in analysis: {line.strip()}")
            continue

        deps[name] = {
            "version": versionn,
        }
    return deps


def get_versions_observed(dep: dict, start_date, end_date) -> int:
    versions = 0
    for v in dep["all_versions"]:
        # if in date range, add it
        date = datetime.strptime(v["date"], '%Y-%m-%dT%H:%M:%S.%f%z')
        if date >= start_date and date <= end_date:
            versions += 1

    return versions


def get_semver_type_update_period(dep: dict, start_date, end_date) -> str:
    start_version = None
    start_version_date = None

    end_version = None
    end_version_date = None

    for v in dep["all_versions"]:
        # if in date range, add it
        date = datetime.strptime(v["date"], '%Y-%m-%dT%H:%M:%S.%f%z')
        if date >= start_date and date <= end_date:
            if start_version is None:
                start_version = v["version"]
                end_version = v["version"]
                start_version_date = date
                end_version_date = date
            elif date < start_version_date:
                start_version = v["version"]
                start_version_date = date
            elif date > end_version_date:
                end_version = v["version"]
                end_version_date = date

    if start_version is None or end_version is None or start_version == end_version:
        return None

    return what_kind_of_update(start_version, end_version)


def main():
    #
    # 1. print usage
    #

    if len(sys.argv) < 2:
        print("./metrics.py <GUPPY_JSON_OUTPUT>")
        return

    #
    # 2. retrieve arguments from files or stdin
    #

    # open datetime files to get period [start_date,end_date]
    f1 = open("release1.datetime", "r")
    start_date = datetime.strptime(f1.read().strip(), '%Y-%m-%d %H:%M:%S %z')

    f2 = open("release2.datetime", "r")
    end_date = datetime.strptime(f2.read().strip(), '%Y-%m-%d %H:%M:%S %z')

    # open dependency files
    f3 = open("release1.deps", "r")
    all_deps = dep_file_to_list(f3.readlines())

    f4 = open("release_latest.deps", "r")
    all_deps_latest = dep_file_to_list(f4.readlines())

    # open analyzed in our codebase during put (dep diff within the period)
    guppy_output_file = sys.argv[1]
    guppy_output = open(guppy_output_file, "r").read()
    guppy = json.loads(guppy_output)

    #
    # 3. filter guppy diff output
    #

    # get runtime deps that have changed
    changed = []
    if "target-packages" in guppy and "changed" in guppy["target-packages"]:
        changed += guppy["target-packages"]["changed"]

    # get build-time deps that have changed
    if "host-packages" in guppy and "changed" in guppy["host-packages"]:
        changed += guppy["host-packages"]["changed"]

    # TODO: how many dep introduced?

    #
    # 5. filter and get info from crates.io
    #

    deps = {}
    print("obtaining info from crates.io...")
    for dep in changed:
        # filter
        if "workspace-path" in dep:
            continue
        if dep["change"] != "modified":
            continue
        if dep["old-version"] is None:
            continue
        assert("version" in dep)

        # TODO: don't ignore this
        if "crates-io" not in dep or dep["crates-io"] != True:
            continue

        # create deps entry from crates.io info
        name = dep["name"]

        if name not in deps:
            # get info from crates.io
            info = get_crate_info(name)

            # extract what's useful from info
            versions = extract_from_info(info)

            # create entry in deps
            deps[name] = {
                "all_versions": versions,
                "old_version": dep["old-version"],
                "new_version": dep["version"],
            }
        # make sure we keep the largest version change when a dependency has been updated several times
        else:
            old_version = version.Version(deps[name]["old_version"])
            new_version = version.Version(deps[name]["new_version"])

            if version.Version(dep["old-version"]) < old_version:
                print(
                    f'debug: old {dep["old-version"]} < {old_version}')
                deps[name]["old_version"] = dep["old-version"]

            if version.Version(dep["version"]) > new_version:
                print(
                    f'debug: new {dep["version"]} > {new_version}')
                deps[name]["new_version"] = dep["version"]

    # do the same with all the deps
    for name in all_deps:
        # get info from crates.io
        info = get_crate_info(name)

        # extract what's useful from info
        versions = extract_from_info(info)

        # update
        all_deps[name]["all_versions"] = versions

    # do the same with all the deps latest
    for name in all_deps_latest:
        # get info from crates.io
        info = get_crate_info(name)

        # extract what's useful from info
        versions = extract_from_info(info)

        # update
        all_deps_latest[name]["all_versions"] = versions

    #
    # 5. compute metrics on landed changes
    #

    versions_landed = 0
    semver_landed = defaultdict(int)

    print("computing metrics...")
    for dep in deps.values():
        # 1. versions changes (v0.1.0 -> v0.1.2 counts for 2 versions)
        versions_landed += get_versions_landed(dep)

        # 2. MAJOR/MINOR/PATCH changes
        sem = get_semver_type_update(dep)
        semver_landed[sem] += 1

    #
    # 6. compute metrics on observed changes (published by crates, but not necessarily landed, in that period of time)
    #

    versions_observed = 0
    semver_observed = defaultdict(int)

    for dep in all_deps.values():
        versions_observed += get_versions_observed(dep, start_date, end_date)
        sem = get_semver_type_update_period(dep, start_date, end_date)
        if sem is not None:
            semver_observed[sem] += 1

    #
    # 7. compute metrics on current situation
    #

    backlog = {}
    backlog_semver = defaultdict(int)
    for name in all_deps_latest:
        sem = get_semver_type_update_period(
            all_deps_latest[name], start_date, end_date)
        if sem is not None:
            backlog[name] = sem
            backlog_semver[sem] += 1

    #
    # 7. print out results
    #

    print(f"{len(deps)} dependencies were updated on the repo, jumping versions {versions_landed} increments higher.")
    print("Eventually, this can be summarized as")
    for sem in semver_landed:
        print(f"- {semver_landed[sem]} {sem} changes")

    print()

    print(f"{len(all_deps)} dependencies were analyzed in our codebase during that time period, which published {versions_observed} new versions")
    print(f"Eventually, this can be summarized as")
    for sem in semver_observed:
        print(f"- {semver_observed[sem]} {sem} changes")

    print()

    print(f"the backlog of {len(backlog)} is {backlog}")
    print(f"the summarized backlog: {backlog_semver}")


if __name__ == "__main__":
    main()
