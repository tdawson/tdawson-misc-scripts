#!/bin/bash
LIST_NAME="packages"
ARCH="x86_64"
DISTRO="rawhide"
NONSTOP="FALSE"
NOREPO="FALSE"
SAVELOGS="FALSE"
NOCLEAN="FALSE"
# make sure there is a file /etc/mock/${MOCK_CONF}.conf
MOCK_CONF="local-8-${ARCH}"
WORK_DIR="${HOME}/rebuild/work"
OUTPUT_DIR="${HOME}/rebuild/output"
LOCAL_REPO_DIR="${HOME}/rebuild/repos/local/${ARCH}"

###############
# Show help
###############
usage() {
  echo "Usage `basename $0` <options>" >&2
  echo >&2
  echo "Reads a list of source package names.  Downloads the srpm rpm from koji" >&2
  echo "  and then builds each package, one at a time." >&2
  echo "This script is best when there are many packages that depend on the build before them." >&2
  echo >&2
  echo "Options:" >&2
  echo "  --nonstop --non-stop" >&2
  echo "    Do not stop if a package fails." >&2
  echo "      Default is to stop if a package fails a build" >&2
  echo "  --savelogs --save-logs" >&2
  echo "    Save the logs of each build." >&2
  echo "      Default is to not save the logs" >&2
  echo "  --norepo --no-repo" >&2
  echo "    Do not put built packages into a local repo" >&2
  echo "      Default is to put build packages into a local repo" >&2
  echo "      That local repo is then regenerated and used for the next build" >&2
  echo "  --noclean --no-clean" >&2
  echo "    Do not clean the mock area after each build." >&2
  echo "      Default is to clean the area after each build." >&2
  echo "  --name [name]" >&2
  echo "    Name of the work area.  Default: ${LIST_NAME} " >&2
  echo "  --mock --mock-cfg [mock_conf]" >&2
  echo "    What mock config to use.  Default: ${MOCK_CONF} " >&2
  echo "  --distro [distro]" >&2
  echo "    Where to download the source from.  Default: ${DISTRO} " >&2
  echo "  -v --verbose --debug" >&2
  echo "    Be verbose, for debugging" >&2
  echo "  -h, --help" >&2
  echo "    Show this options menu" >&2
  echo >&2
  popd &>/dev/null
  exit 1
}

###############
# Get our arguments
###############
while [[ "$#" -ge 1 ]]
do
key="$1"
case $key in
    --nonstop | --non-stop )
      export NONSTOP="TRUE"
    ;;
    --savelogs | --save-logs )
      export SAVELOGS="TRUE"
    ;;
    --norepo | --no-repo )
      export NOREPO="TRUE"
    ;;
    --noclean | --no-clean )
      export NOCLEAN="TRUE"
    ;;
    --name )
      export LIST_NAME="${2}"
      shift
    ;;
    --mock | --mock-cfg )
      export MOCK_CONF="${2}"
      shift
    ;;
    --distro )
      export DISTRO="${2}"
      shift
    ;;
    -v | --verbose | --debug)
      export VERBOSE="TRUE"
    ;;
    -h | --help )
      usage
      exit 1
    ;;
    *)
      PACKAGE_LIST="${PACKAGE_LIST} ${key}"
    ;;
esac
shift # past argument or value
done

###############
# Variables, Part 2
###############
QUEUE_FILE="${WORK_DIR}/${LIST_NAME}/${LIST_NAME}.queue"
DONE_FILE="${WORK_DIR}/${LIST_NAME}/${LIST_NAME}.done"
SRPM_DIR="${WORK_DIR}/${LIST_NAME}/srpms"
DONE_DIR="${WORK_DIR}/${LIST_NAME}/done"
LOG_DIR="${WORK_DIR}/${LIST_NAME}/logs"
WORK_LOG="${LOG_DIR}/work.log"
SOURCE_REPO="${DISTRO}-source"
if [ "${DISTRO}" == "rawhide" ] ; then
  ALT_SOURCE_REPO="${DISTRO}-source"
else
  ALT_SOURCE_REPO="${DISTRO}-updates-source"
fi

###############
# Setup
###############
mkdir -p ${OUTPUT_DIR}/${LIST_NAME}/{source,os}/Packages/
mkdir -p ${WORK_DIR}/${LIST_NAME}/{srpms,logs,done}
mkdir -p ${LOCAL_REPO_DIR}/${LIST_NAME}-Packages/
echo "==== $(date) ====" >> ${WORK_LOG}

cat ${QUEUE_FILE} | while read package
do
  echo "WORKING ON: ${package}"
  echo "WORKING ON: ${package}" >> ${WORK_LOG}
  cd ${SRPM_DIR}
  rm -f *.src.rpm
  dnf --disablerepo=* --enablerepo=${SOURCE_REPO} --source download ${package}
  if [ $? -gt 0 ] ; then
    echo "  Not in original repo, pulling from alt source repo"
    dnf --disablerepo=* --enablerepo=${ALT_SOURCE_REPO} --source download ${package}
    if [ $? -gt 0 ] ; then
      echo "  FAILURE"
      echo "    Unable to download: ${package}"
      echo "    Unable to download: ${package}" >> ${WORK_LOG}
      if ! [ "${NONSTOP}" == "TRUE" ] ; then
        exit 3
      fi
    else
      echo "${package} $(rpm -qp --qf='%{name}-%{version}-%{release}' *.src.rpm) ${ALT_SOURCE_REPO}" >> ${WORK_LOG}
    fi
  else
    echo "${package} $(rpm -qp --qf='%{name}-%{version}-%{release}' *.src.rpm) ${SOURCE_REPO}" >> ${WORK_LOG}
  fi
  this_src_rpm="$(ls -1 *src.rpm)"
  if [ "${NOCLEAN}" == "TRUE" ] ; then
    mock -r ${MOCK_CONF} --no-clean --rebuild ${this_src_rpm}
  else
    mock -r ${MOCK_CONF} --no-clean --rebuild ${this_src_rpm}
  fi
  if [ $? -eq 0 ] ; then
    echo "  SUCCESS: ${package}"
    echo "  SUCCESS: ${package}" >> ${WORK_LOG}
    
    mv ${this_src_rpm} ${DONE_DIR}
    echo ${package} >> ${DONE_FILE}
    sed -i "/^${package}$/d" ${QUEUE_FILE}
    
    if ! [ "${NOREPO}" == "TRUE" ] ; then
      rm -f /var/lib/mock/${MOCK_CONF}/result/*{debuginfo,debugsource}*.rpm
      mv /var/lib/mock/${MOCK_CONF}/result/*.src.rpm ${OUTPUT_DIR}/${LIST_NAME}/source/Packages/
      cp -f /var/lib/mock/${MOCK_CONF}/result/*.rpm ${LOCAL_REPO_DIR}/${LIST_NAME}-Packages/
      mv /var/lib/mock/${MOCK_CONF}/result/*.rpm ${OUTPUT_DIR}/${LIST_NAME}/os/Packages/
      createrepo --update ${LOCAL_REPO_DIR}/
    fi
    if [ "${SAVELOGS}" == "TRUE" ] ; then
      mkdir -p ${LOG_DIR}/success/${package}
      cp -f /var/lib/mock/${MOCK_CONF}/result/*log ${LOG_DIR}/success/${package}
    fi
  else
    echo "  FAILURE"
    echo "    Unable to build: ${package}"
    echo "    Unable to build: ${package}" >> ${WORK_LOG}
    if [ "${SAVELOGS}" == "TRUE" ] ; then
      mkdir -p ${LOG_DIR}/failure/${package}
      cp -f /var/lib/mock/${MOCK_CONF}/result/*log ${LOG_DIR}/failure/${package}
    fi
    if ! [ "${NONSTOP}" == "TRUE" ] ; then
      exit 5
    fi
  fi
done
