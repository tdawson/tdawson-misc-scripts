#!/usr/bin/python3

import sys
import argparse
import copy
import dnf
import dnf.cli
import dnf.exceptions
import dnf.rpm.transaction
import dnf.yum.rpmtrans
import libdnf.repo
import os
import rpm
import shutil
import tempfile

# Arguments
parser = argparse.ArgumentParser()
parser.add_argument("arch", help="What arch are we using",
        choices=["aarch64", "ppc64le", "s390x", "x86_64"])
parser.add_argument("repo", help="What repo are we using",
        choices=["rawhide", "centos"])
args = parser.parse_args()
repoName = args.repo
repoBase = args.repo
if args.repo == "rawhide":
    releasever = "33"
elif args.repo == "centos":
    releasever = "8"
arch = args.arch


# Configuration
workDir = "./"
repoConfDir = workDir + "repos/"
outputDir = "./"
installroot = "/installroot-" + arch

# Lists
listQueue = open("./package.list").read().splitlines()
#listQueue =['bash', 'sedd', 'systemd']


print(arch + ": Setup")
base = dnf.Base()
base.conf.read(repoConfDir + repoName + "." + arch + ".repo")
base.conf.substitutions['releasever'] = releasever
base.conf.installroot = installroot
base.conf.arch = arch

base.read_all_repos()
base.fill_sack(load_system_repo=False)

print(arch + ": Working on Packages")
for this_binary in listQueue:
  #print('.', end='')
  #print('.', end='', flush=True)
  print(arch + ":   " + this_binary)
  base.reset(goal='true')
  ## See if we can attempt to install
  try:
    base.install(this_binary)
  except dnf.exceptions.MarkingError as e:
    print(arch + ":     Cannot Find Package: " + this_binary)
    print(e)
    fileNoInstall=open(outputDir + "errors/NotFound", "a+")
    fileNoInstall.write(this_binary + "\n")
    fileNoInstall.close()
  
  ## Resolve, or fake-install, the package.
  try:
      base.resolve()
      ## We were successful fake installing, use this information
  ## We could not install all the BuildRequires, let us know somehow
  except dnf.exceptions.DepsolveError as e:
      print(arch + ": No Resolution for" + this_binary)
      print(e)
      fileBadDeps=open(outputDir + "errors/" + this_binary + "-BadDeps", "a+")
      fileBadDeps.write("===============================\n")
      fileBadDeps.write("ERROR: %s\n" % (this_binary))
      fileBadDeps.write("%s\n" % (e))
      fileBadDeps.close()


print('')
print(arch + ": FINISHED")
