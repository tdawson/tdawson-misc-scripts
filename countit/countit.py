#!/usr/bin/python3
import concurrent.futures
import datetime
import dnf
import glob
import json
import koji
import os
import urllib

from jinja2 import Template
from pathlib import Path

## Variables
installroot = "/installroot"
baseURL = "https://kojipkgs.fedoraproject.org//packages"
archList = ["x86_64"]
#archList = ["aarch64", "ppc64le", "s390x", "x86_64"]
# Colors
color_good = "#00ff00"
color_bad = "#ff0000"
color_not = "#d9ccd3"

# Lists/Dicts
mainDict = {}
mainList = []

# DNF Bases
def get_base(repo_info):
  this_base = dnf.Base()
  conf = this_base.conf
  conf.cachedir = "/var/tmp/countit-dnf-cache-" + repo_info['OtherRepoName']
  conf.installroot = installroot
  this_base.repos.add_new_repo(repo_info['OtherRepoName'], conf, baseurl=[repo_info['OtherRepoURL']])
  return this_base


with open('countit-config.json') as json_file:
  input_config = json.load(json_file)
    
for this_repo in input_config['repos']:
  #print('RepoName: ' + this_repo['RepoName'])
  #print('RepoURL: ' + this_repo['RepoURL'])
  #print('CheckTest: ' + this_repo['CheckTest'])
  #print('CheckInstall: ' + this_repo['CheckInstall'])
  #print('CheckBuild: ' + this_repo['CheckBuild'])
  #print('TestRepoURL: ' + this_repo['TestRepoURL'])
  #print('OtherRepos: ' + str(this_repo['OtherRepos']))
  print("")
  print("Working On: " + this_repo['RepoName'])
  this_overall = {}
  this_spkg_list = {}
  this_bpkg_name_list = []
  ci_bad_binary = []
  cb_bad_builds = []
  test_this_spkg_list = {}
  test_ci_bad_binary = []
  test_cb_bad_builds = []
  this_overall["reponame"] = this_repo['RepoName']

  # Gather a list of all binary packages in all other repos.
  # print('  OtherRepos: ' + str(this_repo['OtherRepos']))
  for other_repo in this_repo['OtherRepos']:
    print("  Gathering binary packages in " + other_repo['OtherRepoName'] + "...", end='')
    this_base = get_base(other_repo)
    this_base.fill_sack(load_system_repo=False)
    query = this_base.sack.query().available()
    other_bpkg_list = query.run()
    print(len(other_bpkg_list))
    if this_repo['RepoName'] in mainDict:
      mainDict[this_repo['RepoName']].append([other_repo['OtherRepoName'], len(other_bpkg_list)])
    else:
      mainDict[this_repo['RepoName']] = [other_repo['OtherRepoName'], len(other_bpkg_list)]
    ## Get the source rpms out of the binary package list
    print("  Updating source package list ... ", end='')
    for bpkg in other_bpkg_list:
      binarynvr = bpkg.name + "-" + bpkg.evr
      sourcenvr = bpkg.sourcerpm.rsplit(".",2)[0]
      sourcename = sourcenvr.rsplit("-",2)[0]
      this_binary = {}
      this_binary['bname'] = bpkg.name
      this_binary['bnvr'] =  binarynvr   
      if sourcename in this_spkg_list:
        this_spkg_list[sourcename]['binaries'].append(this_binary)
      else:
        this_source = {}
        this_source['sname'] = sourcename
        this_source['snvr'] = sourcenvr
        this_source['binaries'] = [this_binary]
        this_spkg_list[sourcename] = this_source
    print(len(this_spkg_list))
    mainDict[this_repo['RepoName']].append(["source", len(this_spkg_list)])
  

print()
print(mainDict)
