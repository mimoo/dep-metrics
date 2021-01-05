import requests
import json
import sys
from packaging import version
import semver
from datetime import datetime

API = "https://crates.io/api/v1/crates"


# obtain crate info
def get_crate_info(crate: str) -> dict:
    r = requests.get(API + "/" + crate)
    if r.status_code != 200:
        print("couldn't query crates.io")
        return
    return r.json()


# get number of versions between two semvers
def versions_between(info: dict, old_version: str, new_version: str) -> int:
    versions = []
    for v in info["versions"]:
        versions.append(v["num"])
    versions = sorted(versions, key=lambda x: version.Version(x))

    return versions.index(new_version) - versions.index(old_version)


# get type of version change between two semvers
def what_kind_of_update(old_version: str, new_version: str) -> str:
    old = semver.VersionInfo.parse(old_version)
    new = semver.VersionInfo.parse(new_version)
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


def versions_in_daterange(info: dict, start_date, end_date) -> int:
    versions = 0
    for v in info["versions"]:
        # if in date range, add it
        date = datetime.strptime(v["created_at"], '%Y-%m-%dT%H:%M:%S.%f%z')
        if date >= start_date and date <= end_date:
            versions += 1

    return versions


def old_new_versions_in_daterange(info: dict, start_date, end_date):
    start_version = None
    start_version_date = None

    end_version = None
    end_version_date = None

    for v in info["versions"]:
        # if in date range, add it
        date = datetime.strptime(v["created_at"], '%Y-%m-%dT%H:%M:%S.%f%z')
        if date >= start_date and date <= end_date:
            if start_version is None:
                start_version = v["num"]
                end_version = v["num"]
                start_version_date = date
                end_version_date = date
            elif date < start_version_date:
                start_version = v["num"]
                start_version_date = date
            elif date > end_version_date:
                end_version = v["num"]
                end_version_date = date

    return start_version, end_version


def main():
    # print usage
    if len(sys.argv) < 2:
        print("./metrics.py <GUPPY_JSON_OUTPUT>")
        return

    # open datetime files to get period [start_date,end_date]
    f1 = open("release1.datetime", "r")
    start_date = datetime.strptime(f1.read().strip(), '%Y-%m-%d %H:%M:%S %z')

    f2 = open("release2.datetime", "r")
    end_date = datetime.strptime(f2.read().strip(), '%Y-%m-%d %H:%M:%S %z')

    # open guppy output (dep diff within the period)
    guppy_output_file = sys.argv[1]
    guppy_output = open(guppy_output_file, "r")
    guppy = json.loads(guppy_output.read())

    # get runtime deps that have changed
    changed = []
    if "target-packages" in guppy and "changed" in guppy["target-packages"]:
        changed += guppy["target-packages"]["changed"]

    # get build-time deps that have changed
    if "host-packages" in guppy and "changed" in guppy["host-packages"]:
        changed += guppy["host-packages"]["changed"]

    # init
    versions_updated = 0
    semver_versions_updated = {}
    dep_to_changes = {}

    dep_to_actual_changes = {}
    actual_changes = 0
    actual_semver_versions_updated = {}

    # TODO: how many dep introduced?

    # fill
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

        # debug
        if dep["name"] == "rand":
            print(dep)

        # get all versions for that dependency
        info = get_crate_info(dep["name"])

        # get number of version updates that happened between the two commits
        versions = versions_between(info, dep["old-version"], dep["version"])
        versions_updated += versions

        # fill dep_to_changes map
        if dep["name"] not in dep_to_changes:
            dep_to_changes[dep["name"]] = versions
        # only update if that version change is larger
        elif dep_to_changes[dep["name"]] < versions:
            dep_to_changes[dep["name"]] = versions

        # is it a MAJOR, MINOR, or PATCH change?
        # TODO: if there are duplicates, it will be reflected here
        # TODO: probably want to go through dep_to_changes at the end to calculate this
        sem = what_kind_of_update(dep["old-version"], dep["version"])
        if sem not in semver_versions_updated:
            semver_versions_updated[sem] = 1
        else:
            semver_versions_updated[sem] += 1

        # get actual version changes during these dates
        if dep["name"] not in dep_to_actual_changes:
            num_changes = versions_in_daterange(
                info, start_date, end_date)
            dep_to_actual_changes[dep["name"]] = num_changes
            actual_changes += num_changes

        # get actual semver version updates in these dates
        old, new = old_new_versions_in_daterange(info, start_date, end_date)
        if old is not None and new is not None and old != new:
            sem = what_kind_of_update(old, new)
            if sem not in actual_semver_versions_updated:
                actual_semver_versions_updated[sem] = 1
            else:
                actual_semver_versions_updated[sem] += 1

    # print out
    print(f"incremental version changes: {versions_updated}")
    print(f"eventual version changes: {semver_versions_updated}")

    biggest_offenders = sorted(
        dep_to_changes, key=dep_to_changes.get, reverse=True)
    print("biggest offenders:")
    for offender in biggest_offenders[:20]:
        print(
            f"- {offender} has had {dep_to_changes[offender]} version changes")

    print(f"actual eventual version changes: {actual_semver_versions_updated}")

    print(f"actual incremental version changes: {actual_changes}")
    actual_biggest_offenders = sorted(
        dep_to_actual_changes, key=dep_to_actual_changes.get, reverse=True)
    print("actual biggest offenders:")
    for offender in actual_biggest_offenders[:20]:
        print(
            f"- {offender} has had {dep_to_actual_changes[offender]} version changes")


if __name__ == "__main__":
    main()
