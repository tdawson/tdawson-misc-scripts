#!/usr/bin/python3

import argparse
import datetime
import dnf
import glob
import json
import koji
import logging
import os
import re
import requests
import rpm

from jinja2 import Template

## Variables
installroot = "/installroot"

# Which arches are we doing
archList = ["x86_64"]
#archList = ["aarch64", "ppc64le", "s390x", "x86_64"]
arch = "x86_64"

# How chatty are we?
#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)




# Import the configuration
with open('find-missing-config.json') as json_file:
  input_config = json.load(json_file)

for this_distro in input_config['distros']:
  # Variables
  missing_list = []
  binary_list = []
  source_list = []
  binary_source_list = {}
  this_spkg_list = {}

  # Connect to Fedora Koji instance
  if this_distro['WhichKoji'] == "koji":
    session = koji.ClientSession('https://koji.fedoraproject.org/kojihub')
  elif this_distro['WhichKoji'] == "brew":
    session = koji.ClientSession('https://brewhub.engineering.redhat.com/brewhub')
  elif this_distro['WhichKoji'] == "stream":
    session = koji.ClientSession('https://kojihub.stream.centos.org/kojihub')

  ## Get list of binary, and source packages
  # Get everything from the repos, in pkg format
  for other_repo in this_distro['RepoList']:
    with dnf.Base() as base:
      conf = base.conf
      conf.cachedir = "/var/tmp/missing-dnf-cache-" + this_distro['DistroName']
      conf.installroot = installroot
      base.repos.add_new_repo(other_repo['RepoName'], conf, baseurl=[other_repo['RepoURL']])
      base.fill_sack(load_system_repo=False)
      query = base.sack.query().available()
      this_bpkg_list = query.run()
      ## Get the source rpms out of the binary package list
      logging.info("  Getting binary and source package list for: {0}".format(other_repo['RepoName']))
      for bpkg in this_bpkg_list:
        binarynvr = bpkg.name + "-" + bpkg.evr
        sourcenvr = bpkg.sourcerpm.rsplit(".",1)[0]
        binary_list.append(binarynvr)
        if sourcenvr not in source_list:
          source_list.append(sourcenvr)
    
  logging.info(" ")
  logging.info("  Total Binaries: " + str(len(binary_list)))
  logging.info("  Total Sources: " + str(len(source_list)))

  # Write out lists
  with open("binary-list.txt", 'w') as b:
    for this_nvr in binary_list:
      b.write("{0}\n".format(this_nvr))
  with open("source-list.txt", 'w') as b:
    for this_nvr in source_list:
      b.write("{0}\n".format(this_nvr))

  # Find out if all the binaries in koji are in the source binary list
  for spkg in source_list:
    logging.debug("SRPM: {0}  BuildID:".format(spkg))
    srpmInfo = session.getRPM(spkg)
    logging.debug("SRPM: {0}  BuildID: {1}".format(spkg, srpmInfo['build_id']))
    rpms = session.listRPMs(buildID=srpmInfo['build_id'], arches=arch)
    for rpm in rpms:
      if "debuginfo" not in rpm['name'] and "debugsource" not in rpm['name']:
        #this_nvra=rpm['nvr']+"."+rpm['arch']
        if rpm['epoch'] :
          this_envr=rpm['name']+"-"+str(rpm['epoch'])+":"+str(rpm['version'])+"-"+str(rpm['release'])
        else:
          this_envr=rpm['nvr']
        if this_envr in binary_list:
          logging.debug("   FOUND: {0} ".format(this_envr))
        else: 
          logging.info("   MISSING: {0} SRPM: {1}".format(this_envr, spkg))
          missing_list.append(this_envr+" "+spkg)

  logging.info(" ")
  logging.info(missing_list)
  logging.info(" ")
  logging.info("  Total Missing: " + str(len(missing_list)))

  # Write out lists
  with open("missing-list.txt", 'w') as b:
    for this_line in missing_list:
      b.write("{0}\n".format(this_line))
