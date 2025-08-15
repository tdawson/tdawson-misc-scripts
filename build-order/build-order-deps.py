#!/usr/bin/python3
import argparse
import datetime
import dnf
import json
import koji
import os
import sys
import urllib.request


# These functions were pulled from Content Resolver Analyzer.py
#####################################################
### Find build dependencies from a Koji root log ###
####################################################

def _get_build_deps_from_a_root_log(root_log):
    """
    Given a packages Koji root_log, find its build dependencies.
    """
    required_pkgs = []

    # The individual states are nicely described inside the for loop.
    # They're processed in order
    state = 0

    for file_line in root_log.splitlines():

        # 0/
        # parts of the log I don't really care about
        if state == 0:

            # The next installation is the build deps!
            # So I start caring. Next state!
            if "'builddep', '--installroot'" in file_line:
                state += 1


        # 1/
        # getting the "already installed" packages to the list
        elif state == 1:

            # "Package already installed" indicates it's directly required,
            # so save it.
            # DNF5 does this after "Repositories loaded" and quotes the NVR;
            # DNF4 does this before "Dependencies resolved" without the quotes.
            if "is already installed." in file_line:
                pkg_name = file_line.split()[3].strip('"').rsplit("-",2)[0]
                required_pkgs.append(pkg_name)

            # That's all! Next state! (DNF4)
            elif "Dependencies resolved." in file_line:
                state += 1

            # That's all! Next state! (DNF5)
            elif "Repositories loaded." in file_line:
                state += 1


        # 2/
        # going through the log right before the first package name
        elif state == 2:

            # "Package already installed" indicates it's directly required,
            # so save it.
            # DNF4 does this before "Dependencies resolved" without the quotes;
            # DNF5 does this after "Repositories loaded" and quotes the NVR, but
            # sometimes prints this in the middle of a dependency line.
            if "is already installed." in file_line:
                pkg_index = file_line.split().index("already") - 2
                pkg_name = file_line.split()[pkg_index].strip('"').rsplit("-",2)[0]
                required_pkgs.append(pkg_name)

            # The next line will be the first package. Next state!
            # DNF5 reports "Installing: ## packages" in the Transaction Summary,
            # which we need to ignore
            if "Installing:" in file_line and len(file_line.split()) == 3:
                state += 1


        # 3/
        # And now just saving the packages until the "installing dependencies" part
        # or the "transaction summary" part if there's no dependencies
        elif state == 3:

            if "Installing dependencies:" in file_line:
                state = 2

            elif "Transaction Summary" in file_line:
                state = 2

            # Sometimes DNF5 prints "Package ... is already installed" in middle of the output.
            elif file_line.split()[2] == "Package" and file_line.split()[-1] == "installed.":
                pkg_name = file_line.split()[3].strip('"').rsplit("-",2)[0]
                required_pkgs.append(pkg_name)

            else:
                # I need to deal with the following thing...
                #
                # DEBUG util.py:446:   gobject-introspection-devel     aarch64 1.70.0-1.fc36              build 1.1 M
                # DEBUG util.py:446:   graphene-devel                  aarch64 1.10.6-3.fc35              build 159 k
                # DEBUG util.py:446:   gstreamer1-plugins-bad-free-devel
                # DEBUG util.py:446:                                   aarch64 1.19.2-1.fc36              build 244 k
                # DEBUG util.py:446:   json-glib-devel                 aarch64 1.6.6-1.fc36               build 173 k
                # DEBUG util.py:446:   libXcomposite-devel             aarch64 0.4.5-6.fc35               build  16 k
                #
                # The "gstreamer1-plugins-bad-free-devel" package name is too long to fit in the column,
                # so it gets split on two lines.
                #
                # Which if I take the usual file_line.split()[2] I get the correct name,
                # but the next line gives me "aarch64" as a package name which is wrong.
                #
                # So the usual line has file_line.split() == 8
                # The one with the long package name has file_line.split() == 3
                # and the one following it has file_line.split() == 7
                #
                # One more thing... long release!
                #
                # DEBUG util.py:446:   qrencode-devel               aarch64 4.0.2-8.fc35                  build  13 k
                # DEBUG util.py:446:   systemtap-sdt-devel          aarch64 4.6~pre16291338gf2c14776-1.fc36
                # DEBUG util.py:446:                                                                      build  71 k
                # DEBUG util.py:446:   tpm2-tss-devel               aarch64 3.1.0-4.fc36                  build 315 k
                #
                # So the good one here is file_line.split() == 5.
                # And the following is also file_line.split() == 5. Fun!
                #
                # So if it ends with B, k, M, G it's the wrong line, so skip, otherwise take the package name.
                #
                # I can also anticipate both get long... that would mean I need to skip file_line.split() == 4.

                if len(file_line.split()) == 10 or len(file_line.split()) == 11:
                    # Sometimes DNF5 prints "Package ... is already installed" in the middle of a line
                    pkg_index = file_line.split().index("already") - 2
                    pkg_name = file_line.split()[pkg_index].strip('"').rsplit("-",2)[0]
                    required_pkgs.append(pkg_name)
                    if pkg_index == 3:
                        pkg_name = file_line.split()[7]
                    else:
                        pkg_name = file_line.split()[2]
                    required_pkgs.append(pkg_name)

                # TODO: len(file_line.split()) == 9 ??

                elif len(file_line.split()) == 8 or len(file_line.split()) == 3:
                    pkg_name = file_line.split()[2]
                    required_pkgs.append(pkg_name)

                elif len(file_line.split()) == 7 or len(file_line.split()) == 4:
                    continue

                elif len(file_line.split()) == 6 or len(file_line.split()) == 5:
                    # DNF5 uses B/KiB/MiB/GiB, DNF4 uses B/k/M/G
                    if file_line.split()[4] in ["B", "KiB", "k", "MiB", "M", "GiB", "G"]:
                        continue
                    else:
                        pkg_name = file_line.split()[2]
                        required_pkgs.append(pkg_name)

                else:
                    raise KojiRootLogError


        # 4/
        # I'm done. So I can break out of the loop.
        elif state == 4:
            break


    return required_pkgs


def _download_root_log_with_retry(root_log_url):
    """
    Download root.log file with retry logic.
    """
    MAX_TRIES = 10
    attempts = 0

    while attempts < MAX_TRIES:
        try:
            with urllib.request.urlopen(root_log_url, timeout=20) as response:
                root_log_data = response.read()
                return root_log_data.decode('utf-8')
        except Exception:
            attempts += 1
            if attempts == MAX_TRIES:
                raise KojiRootLogError(f"Could not download root.log from {root_log_url}")
            time.sleep(1)

def _get_koji_log_path(srpm_nvr, build_id, arch, koji_session):
    """
    Get koji log path for a given SRPM.
    """
    MAX_TRIES = 10
    attempts = 0

    while attempts < MAX_TRIES:
        try:
            koji_logs = koji_session.getBuildLogs(build_id)
            break
        except Exception:
            attempts += 1
            if attempts == MAX_TRIES:
                raise KojiRootLogError("Could not talk to Koji API")
            time.sleep(1)

    koji_log_path = None
    for koji_log in koji_logs:
        if koji_log["name"] == "root.log":
            if koji_log["dir"] == arch or koji_log["dir"] == "noarch":
                koji_log_path = koji_log["path"]
                break

    return koji_log_path


def process_single_srpm_root_log(work_item):
    """
    Process a single SRPM's root.log file.

    Args:
        work_item (dict): Contains koji_api_url, koji_files_url, srpm_nvr, arch, dev_buildroot

    Returns:
        dict: Contains srpm_nvr, arch, deps (list), error (str or None)
    """
    try:
        koji_api_url = work_item['koji_api_url']
        koji_files_url = work_item['koji_files_url']
        arch = work_item['arch']
        srpm_nvr = work_item['srpm_nvr']
        srpm_buildid = work_item['srpm_buildid']

        # Create koji session
        koji_session = koji.ClientSession(koji_api_url)

        # # Get latest nvr
        # print("Getting the latest source nvr")
        # srpm_nvr = _get_latest_srpm_nvr(work_item, koji_session)

        # Get koji log path
        # print("    Getting the log path for: {}".format(srpm_nvr))
        koji_log_path = _get_koji_log_path(srpm_nvr, srpm_buildid, arch, koji_session)

        if not koji_log_path:
            return {
                'srpm_nvr': srpm_nvr,
                'arch': arch,
                'deps': [],
                'error': None
            }

        # Download root.log
        # print("    Getting the root log for: {}".format(srpm_nvr))
        root_log_url = f"{koji_files_url}/{koji_log_path}"
        root_log_contents = _download_root_log_with_retry(root_log_url)

        # Parse dependencies
        # print("    Parsing the root log for: {}".format(srpm_nvr))
        deps = _get_build_deps_from_a_root_log(root_log_contents)

        return {
            'srpm_nvr': srpm_nvr,
            'arch': arch,
            'deps': deps,
            'error': None
        }

    except Exception as e:
        return {
            'srpm_nvr': work_item.get('srpm_nvr', 'unknown'),
            'arch': work_item.get('arch', 'unknown'),
            'deps': [],
            'error': str(e)
        }


parser = argparse.ArgumentParser()
parser.add_argument("--tag", dest="tag", default="f42", help="Tag to get the latest nvrs for")
parser.add_argument("--output", dest="output", default="deps", help="Directory to put the output")
parser.add_argument("--input", dest="input", default="file-list", help="File with the package list, one name per line")
args = parser.parse_args()


koji_files_url = "https://kojipkgs.fedoraproject.org"
koji_api_url = "https://koji.fedoraproject.org/kojihub"
arch = "x86_64"
tag_id = args.tag
tag_update_id = "{}-updates".format(tag_id)
output_dir = args.output
# srpm_list = ["plasma-workspace", "kf6", "kate", "libpng", "blahblah"]
with open(args.input) as file:
    srpm_list = [line.rstrip() for line in file]

# Gather all the nvrs, buildid, and anything else,
#  Then put them into the work_items
print("Gathering list of nvrs")
session = koji.ClientSession(koji_api_url)
latest_builds = session.listTagged(tag_id, latest=True)
latest_update_builds = session.listTagged(tag_update_id, latest=True)

print("Adding data to work_items")
found_srpm = []
work_items = []
# Add to work queue
for pkg in latest_update_builds:
    if pkg["package_name"] in srpm_list :
        srpm_name = pkg["package_name"]
        srpm_nvr = pkg["nvr"]
        srpm_buildid = pkg["build_id"]
        print("  {} was found in {}".format(srpm_name, tag_update_id))
        work_items.append({
            'koji_api_url': koji_api_url,
            'koji_files_url': koji_files_url,
            'arch': arch,
            'srpm_name': srpm_name,
            'srpm_nvr': srpm_nvr,
            'srpm_buildid': srpm_buildid
        })
        found_srpm.append(srpm_name)
for pkg in latest_builds:
    if pkg["package_name"] not in found_srpm :
        if pkg["package_name"] in srpm_list :
            srpm_name = pkg["package_name"]
            srpm_nvr = pkg["nvr"]
            srpm_buildid = pkg["build_id"]
            print("  {} was found in {}".format(srpm_name, tag_id))
            work_items.append({
                'koji_api_url': koji_api_url,
                'koji_files_url': koji_files_url,
                'arch': arch,
                'srpm_name': srpm_name,
                'srpm_nvr': srpm_nvr,
                'srpm_buildid': srpm_buildid
            })
            found_srpm.append(pkg["package_name"])

for pkg in srpm_list:
    if pkg not in found_srpm :
        print("  WARNING:  {} was not found".format(pkg))

print("Processing:")
os.makedirs(output_dir, exist_ok=True)

for work_item in work_items:
    print("  {}".format(work_item["srpm_name"]))
    my_deps = process_single_srpm_root_log(work_item)
    output_file = os.path.join(output_dir, work_item["srpm_name"])
    with open(output_file, 'w') as f:
        for dep in my_deps["deps"]: f.write(dep+"\n")


    # print()
    # print("Deps List:")
    # print(my_deps["deps"])
    # print()

