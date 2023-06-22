#!/usr/bin/python3
# Find the nvr of the packages tagged with a certain tag
# Documentation:
#    https://koji.fedoraproject.org/koji/api
#      listTagged
#    /usr/lib/python3.6/site-packages/koji_cli/commands.py
#      def anon_handle_list_tagged
#        Good examples and explanation of each option
#
# Note:  The first run takes several hours on a full distribution
#        After that, it just does the changes so does not take very long

import koji
import json
import os

# tag="c9s-pending"
# tag="eln"
# kojihub="https://kojihub.stream.centos.org/kojihub"
kojihub="https://koji.fedoraproject.org/kojihub"
current_packagelist="pkglist.json"
old_packagelist="old.pkglist.json"
current_packagelist_text="pkglist.nvr-hash.txt"
spkg_list = {}
old_spkg_list = {}

# Load in previous packagelist if there is one
if os.path.exists(current_packagelist):
  with open(current_packagelist) as json_file:
    spkg_list = json.load(json_file)

# Load in old packagelist if there is one
if os.path.exists(old_packagelist):
  with open(old_packagelist) as json_file:
    old_spkg_list = json.load(json_file)

# Open our session and get the latest builds
session = koji.ClientSession(kojihub)
latest_builds = session.listTagged(tag, latest=True)

# Check if there are any new builds
for pkg in latest_builds:
  if pkg["package_name"] in spkg_list :
    if spkg_list[pkg["package_name"]]["nvr"] == pkg["nvr"] :
      print("    SAME OLD PACKAGE: "+pkg["package_name"]+" NVR: "+pkg["nvr"])
    else :
      print("  OLD BUT NEW: "+pkg["package_name"]+" NVR: "+pkg["nvr"])
      if pkg["package_name"] in old_spkg_list :
        old_spkg_list[pkg["package_name"]][spkg_list[pkg["package_name"]]["nvr"]] = spkg_list[pkg["package_name"]]["githash"]
      else :
        old_spkg_list[pkg["package_name"]] = {spkg_list[pkg["package_name"]]["nvr"]: spkg_list[pkg["package_name"]]["githash"]}
      try:
        buildinfo=session.getBuild(pkg["nvr"])
        spkg_list[pkg["package_name"]] = {"nvr": pkg["nvr"], "githash": buildinfo["source"]}
      except IOError:
        spkg_list[pkg["package_name"]] = {"nvr": pkg["nvr"], "githash": "empty"}

  else :
    print("NEW PACKAGE: "+pkg["package_name"]+" NVR: "+pkg["nvr"])
    try:
      buildinfo=session.getBuild(pkg["nvr"])
      spkg_list[pkg["package_name"]] = {"nvr": pkg["nvr"], "githash": buildinfo["source"]}
    except IOError:
      spkg_list[pkg["package_name"]] = {"nvr": pkg["nvr"], "githash": "empty"}


with open(current_packagelist, "w") as json_file:
  json.dump(spkg_list, json_file)

with open(old_packagelist, "w") as json_file:
  json.dump(old_spkg_list, json_file)

## If you would like this as plain text file uncomment the following
#with open(current_packagelist_text, "w") as text_file:
#  for pkg in spkg_list :
#    text_file.write("%s %s\n" %(pkg, spkg_list[pkg]["githash"]))

