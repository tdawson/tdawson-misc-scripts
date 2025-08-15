#!/usr/bin/python3
# Find the nvr of the packages tagged with a certain tag
# Documentation:
#    https://koji.fedoraproject.org/koji/api
#      listTagged
#    /usr/lib/python3.6/site-packages/koji_cli/commands.py
#      def anon_handle_list_tagged
#        Good examples and explanation of each option
#

import argparse
import json
import koji
import os

# kojihub="https://kojihub.stream.centos.org/kojihub"
kojihub="https://koji.fedoraproject.org/kojihub"

parser = argparse.ArgumentParser()
parser.add_argument("--tag", dest="tag", default="f42-updates", help="Tag to get the latest nvrs for")
args = parser.parse_args()

tag = args.tag
current_packagelist="pkglist.{}.json".format(tag)
test_packagelist="test.pkglist.{}.json".format(tag)
current_packagelist_text="pkglist.{}.name-nvr.txt".format(tag)
spkg_list = {}
old_spkg_list = {}


# Open our session and get the latest builds
session = koji.ClientSession(kojihub)
latest_builds = session.listTagged(tag, latest=True)

# Trim down to just name and nvr
for pkg in latest_builds:
      spkg_list[pkg["package_name"]] = {"nvr": pkg["nvr"]}

with open(current_packagelist, "w") as json_file:
  json.dump(spkg_list, json_file)

with open(current_packagelist_text, "w") as text_file:
  for pkg in spkg_list :
    text_file.write("%s %s\n" %(pkg, spkg_list[pkg]["nvr"]))

