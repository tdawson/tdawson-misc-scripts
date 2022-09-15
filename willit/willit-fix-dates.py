#!/usr/bin/python3
import concurrent.futures
import datetime
import glob
import json
import os
import pprint
import shutil

from pathlib import Path

## Variables
# Lists/Dicts
mainDict = {}
mainList = []
repos=["epel7", "epel8", "epel9", "epel8-next", "epel9-next"]

## Repo Section
for this_repo in repos:
  print("")
  print("Working On: " + this_repo)

  ## Input Everything
  # Get the original json
  try:
    with open('output/' + this_repo + '/status-repo.json', 'r') as jsonfile:
      old_repo = json.load(jsonfile)
  except IOError as e:
    print("Error: {}".format(str(e)))
  # Load in the date-sname data
  try:
    with open(this_repo + '.trim-date-sname', 'r') as input:
      date_sname = {}
      for line in input:
        sline=line.split()
        date_sname[sline[1]]=sline[0]
  except IOError as e:
    print("Error: {}".format(str(e)))
  # Load in the date-snvr data
  try:
    with open(this_repo + '.full-date-snvr', 'r') as input:
      date_snvr = {}
      for line in input:
        sline=line.split()
        date_snvr[sline[1]]=sline[0]
  except IOError as e:
    print("Error: {}".format(str(e)))

  ## Update dates in the json
  for pkg in old_repo['spkg_list'].keys():
    try:
        old_repo['spkg_list'][pkg]['sname_day'] = date_sname[pkg]
    except KeyError:
        print("  Error: sname {}".format(pkg))
    try:
        old_repo['spkg_list'][pkg]['snvr_day'] = date_snvr[old_repo['spkg_list'][pkg]['snvr']]
    except KeyError:
        print("  Error: snvr {}".format(pkg))
        #print(old_repo['spkg_list'][pkg]['snvr_day'])
        #print(old_repo['spkg_list'][pkg]['sname_day'])
        #print(date_sname)
        #print(date_snvr[old_repo['spkg_list'][pkg]['snvr']])

  ## Outpu Everything
  with open('output/' + this_repo + '/status-repo.fix-dates.json', 'w') as w:
    json.dump(old_repo, w)
