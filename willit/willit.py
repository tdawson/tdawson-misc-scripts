#!/usr/bin/python3
import concurrent.futures
import datetime
import dnf
import glob
import json
import koji
import os
import urllib
import shutil

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
def get_base(style, repo_info):
  this_base = dnf.Base()
  conf = this_base.conf
  conf.cachedir = "/var/tmp/willit-dnf-cache-" + repo_info['RepoName']
  conf.installroot = installroot
  if style == "main":
    this_base.repos.add_new_repo(repo_info['RepoName'], conf, baseurl=[repo_info['RepoURL']])
  elif style == "testing":
    this_base.repos.add_new_repo(repo_info['RepoName'] + "testing", conf, baseurl=[repo_info['TestRepoURL']])
  elif style == "main-all":
    this_base.repos.add_new_repo(repo_info['RepoName'], conf, baseurl=[repo_info['RepoURL']])
    for other_repo in repo_info['OtherRepos']:
      this_base.repos.add_new_repo(other_repo['OtherRepoName'], conf, baseurl=[other_repo['OtherRepoURL']])
  elif style == "testing-all":
    this_base.repos.add_new_repo(repo_info['RepoName'], conf, baseurl=[repo_info['RepoURL']])
    this_base.repos.add_new_repo(repo_info['RepoName'] + "testing", conf, baseurl=[repo_info['TestRepoURL']])
    for other_repo in repo_info['OtherRepos']:
      this_base.repos.add_new_repo(other_repo['OtherRepoName'], conf, baseurl=[other_repo['OtherRepoURL']])
  return this_base

# Will the pkg install using the corresponding repos
def will_pkg_install(pkg, style, repo_info):
  this_status = {"status": "pass", "error": ""}
  with dnf.Base() as base:
    conf = base.conf
    conf.cachedir = "/var/tmp/willit-dnf-cache-" + repo_info['RepoName']
    conf.installroot = installroot
    if style == "main":
      base.repos.add_new_repo(repo_info['RepoName'], conf, baseurl=[repo_info['RepoURL']])
      for other_repo in repo_info['OtherRepos']:
        base.repos.add_new_repo(other_repo['OtherRepoName'], conf, baseurl=[other_repo['OtherRepoURL']])
    elif style == "testing":
      base.repos.add_new_repo(repo_info['RepoName'], conf, baseurl=[repo_info['RepoURL']])
      base.repos.add_new_repo(repo_info['RepoName'] + "testing", conf, baseurl=[repo_info['TestRepoURL']])
      for other_repo in repo_info['OtherRepos']:
        base.repos.add_new_repo(other_repo['OtherRepoName'], conf, baseurl=[other_repo['OtherRepoURL']])
    base.fill_sack(load_system_repo=False)
    base.install(pkg)
    try:
      base.resolve()
    except dnf.exceptions.DepsolveError as e:
      this_status['status'] = "fail"
      this_status['error'] = e
  return this_status

# Will the sourcepkg build using the corresponding repos
def will_pkg_build(pkg, name_list, repo_name, koji_session):
  this_status = {"status": "pass", "error": ""}
  this_missing_packages = []
  this_build = koji_session.listTagged(repo_name,package=pkg,latest=True)[0]
  logURL = baseURL+"/"+pkg+"/"+this_build['version']+"/"+this_build['release']+"/data/logs/"
  print()
  print(pkg)
  try:
    root_log = urllib.request.urlopen(logURL+"noarch/root.log")
    test = 1
  except Exception as ex:
    print("No logs for: " + logURL+"noarch/root.log")
    test = 0
  if test == 1:
    this_check = parse_root_log(root_log, name_list)
    if len(this_check) > 0:
      this_missing_packages.append(this_check)    
  else:
    for arch in archList:
      try:
        root_log = urllib.request.urlopen(logURL+arch+"/root.log")
        test = 1
      except Exception as ex:
        print("No logs for: " + logURL+arch+"/root.log")
        test = 0
      if test == 1:
        this_check = parse_root_log(root_log, name_list)
        if len(this_check) > 0:
          this_missing_packages.append(this_check)
  if len(this_missing_packages) > 0:
      this_status['status'] = "fail"
      this_status['error'] = this_missing_packages
  return this_status

# Return a list of just the names
def get_names(pkg_list):
  this_names = []
  for bpkg in pkg_list:
    this_names.append(bpkg.name)
  return this_names
  
# Parse root log.  Return any packages not in packagelist
def parse_root_log(root_log, name_list):
  not_found = []
  # parseStatus
  # 1: top, 2: base required packages 3: base other packages
  # 4: middle, 5: add already installed 6: add required packages
  # 7: add other packages, 8: bottom
  parseStatus = 1
  check = 0
  line = root_log.readline().decode('utf-8').split()
  while line:
      #print("    Status: " + str(parseStatus))
      #print(line)
      if len(line) >2 :
          if parseStatus == 1:
              if '=================' in str(line[2]):
                  if check == 0:
                      check = 1
                  else:
                      check = 0
                      parseStatus = 2
                      #print("    Status: " + str(parseStatus))
                      tmpline = root_log.readline()
          elif parseStatus == 2:
              if line[2] == "Installing":
                  parseStatus = 3
                  #print("    Status: " + str(parseStatus))
              else:
                  #print("Base Required: " + str(line[2]))
                  if not line[2] in name_list:
                    not_found.append(line[2])
          elif parseStatus == 3:
              if line[2] == "Transaction":
                  parseStatus = 4
                  #print("    Status: " + str(parseStatus))
                  tmpline = root_log.readline()
              elif line[2] == "Installing":
                  tmpline = root_log.readline()
              else:
                  #print("Base Runtime Dependency: " + line[2])
                  if not line[2] in name_list:
                    not_found.append(line[2])                  
          elif parseStatus == 4:
              if "=================" in str(line[2]):
                  if check == 0:
                      check = 1
                  else:
                      check = 0
                      parseStatus = 5
                      #print("    Status: " + str(parseStatus))
                      tmpline = root_log.readline()
          elif parseStatus == 5:
              if line[2] == "Installing":
                  parseStatus = 6
                  #print("    Status: " + str(parseStatus))
                  tmpline = root_log.readline()
              else:
                  #print("Required: " + str(line[2]))
                  if not line[2] in name_list:
                    not_found.append(line[2])
          elif parseStatus == 6:
              if line[2] == "Transaction":
                  parseStatus = 8
                  #print("    Status: " + str(parseStatus))
                  tmpline = root_log.readline()
              else:
                  #print("Required Dependency: " + line[2])
                  if not line[2] in name_list:
                    not_found.append(line[2])                  
      line = root_log.readline().decode('utf-8').split()
  return not_found

with open('willit-config.json') as json_file:
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
  shutil.rmtree("/var/tmp/willit-dnf-cache-" + this_repo['RepoName'], ignore_errors=True)
  
  ## Gather a list of all binary packages in main repo.
  print("  Gathering binary packages in repo ... ", end='')
  with dnf.Base() as base:
    conf = base.conf
    conf.cachedir = "/var/tmp/willit-dnf-cache-" + this_repo['RepoName']
    base.repos.add_new_repo(this_repo['RepoName'], conf, baseurl=[this_repo['RepoURL']])
    base.fill_sack(load_system_repo=False)
    query = base.sack.query().available()
    this_bpkg_list = query.run()
    print(len(this_bpkg_list))
    print("  Gathering binary packages in other repos also ... ", end='')
    for other_repo in this_repo['OtherRepos']:
      base.repos.add_new_repo(other_repo['OtherRepoName'], conf, baseurl=[other_repo['OtherRepoURL']])
    base.fill_sack(load_system_repo=False)
    full_query = base.sack.query().available()
    this_full_bpkg_list = full_query.run()
    print(len(this_full_bpkg_list))

  
  ## Get the source rpms out of the binary package list
  print("  Generating source package list ... ", end='')
  for bpkg in this_bpkg_list:
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
      this_source['bad_install'] = []
      this_source['bad_build'] = []
      this_spkg_list[sourcename] = this_source
  print(len(this_spkg_list))
    
  this_overall["bnumber"] = len(this_bpkg_list)
  this_overall["snumber"] = len(this_spkg_list)
  this_bpkg_name_list = this_bpkg_name_list + get_names(this_full_bpkg_list)
  print("  Total Binaries thus far: " + str(len(this_bpkg_name_list)))

  #Gather a list of all binary packages in all other repos.
  #print('  OtherRepos: ' + str(this_repo['OtherRepos']))
  #for other_repo in this_repo['OtherRepos']:
    #print("  Gathering binary packages in " + other_repo['OtherRepoName'])
  #for other_repo in this_repo['OtherRepos']:
    #print("  Gathering binary packages in " + other_repo['OtherRepoName'] + "...", end='')
    #with dnf.Base() as base:
      #conf = base.conf
      #conf.cachedir = "/var/tmp/willit-dnf-cache-" + other_repo['OtherRepoName']
      #base.repos.add_new_repo(other_repo['OtherRepoName'], conf, baseurl=[other_repo['OtherRepoURL']])
      #base.fill_sack(load_system_repo=False)
      #query = base.sack.query().available()
      #other_bpkg_list = query.run()
    #print(len(other_bpkg_list))
    #this_bpkg_name_list = this_bpkg_name_list + get_names(other_bpkg_list)
    #print("  Total Binaries thus far: " + str(len(this_bpkg_name_list)))
  #print("  Total Binaries in all repos: " + str(len(this_bpkg_name_list)))
  

  # Will It Install
  if this_repo['CheckInstall'] == "True":
    this_overall["test_install"] = "True"
    print("  Starting CheckInstall")
    for bpkg in this_bpkg_list:
      #print(".", end='')
      with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
        bpkg_status = executor.submit(will_pkg_install, bpkg.name, "main", this_repo).result()
      #bpkg_status = will_pkg_install(bpkg.name, "main", this_repo)
      if bpkg_status['status'] == "fail":
        binarynvr = bpkg.name + "-" + bpkg.evr
        sourcenvr = bpkg.sourcerpm.rsplit(".",2)[0]
        sourcename = sourcenvr.rsplit("-",2)[0]
        bbinary = {}
        bbinary['bname'] = bpkg.name
        bbinary['bnvr'] = binarynvr
        bbinary['sname'] = sourcename
        bbinary['error'] = bpkg_status['error']
        ci_bad_binary.append(bbinary)
        this_spkg_list[sourcename]['bad_install'].append(bbinary)
        print("    Wont Install: " + binarynvr)
        
    print("      Failed Installs: " + str(len(ci_bad_binary)))
    this_overall["ci_bnumber_good"] = this_overall["bnumber"] - len(ci_bad_binary)
    this_overall["ci_bnumber_bad"] = len(ci_bad_binary)
    if len(ci_bad_binary) > 0:
      this_overall["ci_bcolor"] = color_bad
    else:
      this_overall["ci_bcolor"] = color_good
  else:
    this_overall["test_install"] = "False"
    this_overall["ci_bnumber_good"] = "--"
    this_overall["ci_bnumber_bad"] = "--"
    this_overall["ci_bcolor"] = color_not

  # Will It Build
  if this_repo['CheckBuild'] == "True":
    this_overall["test_build"] = "True"
    print("  Starting CheckBuild")
    this_spkg_list = ["kate"]
    infra = koji.ClientSession('https://koji.fedoraproject.org/kojihub')
    for spkg in this_spkg_list:
      spkg_status = will_pkg_build(spkg, this_bpkg_name_list, this_repo['RepoName'], infra)
      if spkg_status['status'] == "fail":
        print("    Wont Build: " + str(spkg))
        print(str(spkg_status))
        bsource = {}
        bsource['bname'] = spkg
        bsource['error'] = spkg_status['error']
        cb_bad_builds.append(bsource)
    this_overall["cb_snumber_good"] = this_overall["snumber"]
    this_overall["cb_snumber_bad"] = this_overall["snumber"] - len(cb_bad_builds)
    if len(cb_bad_builds) > 0:
      this_overall["cb_scolor"] = color_bad
    else:
      this_overall["cb_scolor"] = color_good
  else:
    this_overall["test_build"] = "False"
    this_overall["cb_snumber_good"] = "--"
    this_overall["cb_snumber_bad"] = "--"
    this_overall["cb_scolor"] = color_not
  
  # Work on Testing if we need to
  if this_repo['CheckTest'] == "True":
    this_overall["test_checked"] = "True"
    ## Gather a list of all binary packages in testing repo.
    print("  Gathering binary packages in testing repo ... ", end='')
    with dnf.Base() as base:
      conf = base.conf
      conf.cachedir = "/var/tmp/willit-dnf-cache-" + this_repo['RepoName']
      base.repos.add_new_repo(this_repo['RepoName'] + "testing", conf, baseurl=[this_repo['TestRepoURL']])
      base.fill_sack(load_system_repo=False)
      query = base.sack.query().available()
      this_bpkg_list = query.run()
    print(len(this_bpkg_list))

    ## Set the source rpms out of the binary package list
    print("  Generating testing source package list ... ", end='')
    for bpkg in this_bpkg_list:
      binarynvr = bpkg.name+"-"+bpkg.evr
      sourcenvr = bpkg.sourcerpm.rsplit(".",2)[0]
      sourcename = sourcenvr.rsplit("-",2)[0]
      this_binary = {}
      this_binary['bname'] = bpkg.name
      this_binary['bnvr'] =  binarynvr   
      if sourcename in test_this_spkg_list:
        test_this_spkg_list[sourcename]['binaries'].append(this_binary)
      else:
        this_source = {}
        this_source['sname'] = sourcename
        this_source['snvr'] = sourcenvr
        this_source['binaries'] = [this_binary]
        this_source['bad_install'] = []
        this_source['bad_build'] = []
        test_this_spkg_list[sourcename] = this_source
    print(len(test_this_spkg_list))

    this_overall["test_bnumber"] = len(this_bpkg_list)
    this_overall["test_snumber"] = len(test_this_spkg_list)

    # Will It Install - For Testing
    if this_repo['CheckInstall'] == "True":
      print("  Starting CheckInstall")
      for bpkg in this_bpkg_list:
        #print(".", end='')
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
          bpkg_status = executor.submit(will_pkg_install, bpkg.name, "testing", this_repo).result()
        #bpkg_status = will_pkg_install(bpkg.name, "testing", this_repo)
        if bpkg_status['status'] == "fail":
          binarynvr = bpkg.name + "-" + bpkg.evr
          sourcenvr = bpkg.sourcerpm.rsplit(".",2)[0]
          sourcename = sourcenvr.rsplit("-",2)[0]
          bbinary = {}
          bbinary['bname'] = bpkg.name
          bbinary['bnvr'] = binarynvr
          bbinary['sname'] = sourcename
          bbinary['error'] = bpkg_status['error']
          test_ci_bad_binary.append(bbinary)
          test_this_spkg_list[sourcename]['bad_install'].append(bbinary)
          print("    Wont Install: " + binarynvr)
          
      print("      Failed Installs: " + str(len(test_ci_bad_binary)))
      this_overall["test_ci_bnumber_good"] = this_overall["test_bnumber"] - len(test_ci_bad_binary)
      this_overall["test_ci_bnumber_bad"] = len(test_ci_bad_binary)
      if len(test_ci_bad_binary) > 0:
        this_overall["test_ci_bcolor"] = color_bad
      else:
        this_overall["test_ci_bcolor"] = color_good
    else:
      this_overall["test_ci_bnumber_good"] = "--"
      this_overall["test_ci_bnumber_bad"] = "--"
      this_overall["test_ci_bcolor"] = color_not

    # Will It Build - For Testing
    if this_repo['CheckBuild'] == "True":
      print("  Starting CheckBuild")
      this_overall["test_cb_snumber_good"] = this_overall["test_snumber"]
      this_overall["test_cb_snumber_bad"] = 2
      this_overall["test_cb_scolor"] = color_bad
    else:
      this_overall["test_cb_snumber_good"] = "--"
      this_overall["test_cb_snumber_bad"] = "--"
      this_overall["test_cb_scolor"] = color_not
  else:
    this_overall["test_checked"] = "FALSE"
    this_overall["test_bnumber"] = "--"
    this_overall["test_snumber"] = "--"
    this_overall["test_ci_bnumber_good"] = "--"
    this_overall["test_ci_bnumber_bad"] = "--"
    this_overall["test_ci_bcolor"] = color_not
    this_overall["test_cb_snumber_good"] = "--"
    this_overall["test_cb_snumber_bad"] = "--"
    this_overall["test_cb_scolor"] = color_not
  
  # Work with data
  mainList.append(this_overall)
  Path("output/" + this_repo['RepoName'] + "/packages").mkdir(parents=True, exist_ok=True)
  Path("output/" + this_repo['RepoName'] + "/testing-packages").mkdir(parents=True, exist_ok=True)
  for pf in glob.glob("output/" + this_repo['RepoName'] + "/*packages/*.html"):
    os.remove(pf)
  with open('templates/status-wont-install.html.jira') as f:
    witmpl = Template(f.read())
  with open('output/' + this_repo['RepoName'] + '/status-wont-install.html', 'w') as w:
    w.write(witmpl.render(
      this_date=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
      badInstall=ci_bad_binary,
      badInstallNum=len(ci_bad_binary),
      testBadInstall=test_ci_bad_binary,
      testBadInstallNum=len(test_ci_bad_binary),
      repo=this_overall))
  with open('templates/status-repo.html.jira') as f:
    tmpl = Template(f.read())
  with open('output/' + this_repo['RepoName'] + '/status-repo.html', 'w') as w:
    w.write(tmpl.render(
      this_date=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
      badInstall=ci_bad_binary,
      badInstallNum=len(ci_bad_binary),
      badBuild=cb_bad_builds,
      badBuildNum=len(cb_bad_builds),
      testBadInstall=test_ci_bad_binary,
      testBadInstallNum=len(test_ci_bad_binary),
      testBadBuild=test_cb_bad_builds,
      testBadBuildNum=len(test_cb_bad_builds),
      thisNum=len(this_spkg_list),
      thisTestNum=len(test_this_spkg_list),
      repo=this_overall))
  with open('templates/index-package.html.jira') as f:
    iptmpl = Template(f.read())
  with open('output/' + this_repo['RepoName'] + '/index-packages.html', 'w') as w:
    w.write(iptmpl.render(
      this_date=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
      repoName=this_repo['RepoName'],
      pkgDir="packages",
      spkgList=this_spkg_list.keys()))
  if this_repo['CheckTest'] == "True":
    with open('output/' + this_repo['RepoName'] + '/index-test-packages.html', 'w') as w:
      w.write(iptmpl.render(
        this_date=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        repoName=this_repo['RepoName'] + "testing",
        pkgDir="testing-packages",
        spkgList=test_this_spkg_list.keys()))
  with open('templates/status-package.html.jira') as f:
    ptmpl = Template(f.read())
  for spkg in this_spkg_list.values() :
    with open('output/' + this_repo['RepoName'] + '/packages/' + spkg['sname'] + '.html', 'w') as w:
      w.write(ptmpl.render(
        this_date=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        repoName=this_repo['RepoName'],
        pkgName=spkg['sname'],
        sNVR=spkg['snvr'],
        binaries=spkg['binaries'],
        binstall=spkg['bad_install'],
        bbuild=spkg['bad_build']))
  if this_repo['CheckTest'] == "True":
    for spkg in test_this_spkg_list.values() :
      with open('output/' + this_repo['RepoName'] + '/testing-packages/' + spkg['sname'] + '.html', 'w') as w:
        w.write(ptmpl.render(
          this_date=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
          color_good=color_good,
          color_bad=color_bad,
          color_not=color_not,
          repoName=this_repo['RepoName'],
          pkgName=spkg['sname'],
          sNVR=spkg['snvr'],
          binaries=spkg['binaries'],
          binstall=spkg['bad_install'],
          bbuild=spkg['bad_build']))
    

# Write out Overall Status Page
Path("output").mkdir(parents=True, exist_ok=True)
with open('templates/status-overall.html.jira') as f:
  tmpl = Template(f.read())
with open('output/status-overall.html', 'w') as w:
  w.write(tmpl.render(
    this_date=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
    color_good=color_good,
    color_bad=color_bad,
    color_not=color_not,
    repos=mainList))
