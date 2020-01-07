#!/bin/bash

this_src_rpm="$1"
if [ "${this_src_rpm}" == "" ] || ! [ -s ${this_src_rpm} ] ; then
  echo " Must give full path to src.rpm"
  exit 1
fi
LIST_NAME="packages"
ARCH="x86_64"
# make sure there is a file /etc/mock/${MOCK_CONF}.conf
MOCK_CONF="local-8-${ARCH}"
WORK_DIR="${HOME}/rebuild/work"
OUTPUT_DIR="${HOME}/rebuild/output"
LOCAL_REPO_DIR="${HOME}/rebuild/repos/local/${ARCH}"
QUEUE_FILE="${WORK_DIR}/${LIST_NAME}/${LIST_NAME}.queue"
DONE_FILE="${WORK_DIR}/${LIST_NAME}/${LIST_NAME}.done"
SRPM_DIR="${WORK_DIR}/${LIST_NAME}/srpms"
DONE_DIR="${WORK_DIR}/${LIST_NAME}/done"
LOG_DIR="${WORK_DIR}/${LIST_NAME}/logs"
WORK_LOG="${LOG_DIR}/work.log"
#SOURCE_REPO="fedora30-updates-source"
#ALT_SOURCE_REPO="fedora30-source"
SOURCE_REPO="rawhide-source"
ALT_SOURCE_REPO="rawhide-source"

# Setup
mkdir -p ${OUTPUT_DIR}/${LIST_NAME}/{source,os}/Packages/
mkdir -p ${WORK_DIR}/${LIST_NAME}/{srpms,logs,done}
mkdir -p ${LOCAL_REPO_DIR}/${LIST_NAME}-Packages/
echo "==== $(date) ====" >> ${WORK_LOG}

package=$(rpm -qp --qf "%{name}" ${this_src_rpm})
if [ "${package}" == "" ] ; then
  echo "  Unable to get package name from: ${this_src_rpm}"
  exit 1
fi

  echo "WORKING ON: ${package}"
  echo "WORKING ON: ${package}" >> ${WORK_LOG}
  # mock -r ${MOCK_CONF} --rebuild ${this_src_rpm}
  # mock -r ${MOCK_CONF} --no-clean --rebuild ${this_src_rpm}
  mock -r ${MOCK_CONF} --no-clean --rebuild ${this_src_rpm}
  if [ $? -eq 0 ] ; then
    echo "  SUCCESS: ${package}"
    echo "  SUCCESS: ${package}" >> ${WORK_LOG}
    
    cp ${this_src_rpm} ${DONE_DIR}
    echo ${package} >> ${DONE_FILE}
    sed -i "/^${package}$/d" ${QUEUE_FILE}
    
    rm -f /var/lib/mock/${MOCK_CONF}/result/*{debuginfo,debugsource}*.rpm
    mv /var/lib/mock/${MOCK_CONF}/result/*.src.rpm ${OUTPUT_DIR}/${LIST_NAME}/source/Packages/
    cp -f /var/lib/mock/${MOCK_CONF}/result/*.rpm ${LOCAL_REPO_DIR}/${LIST_NAME}-Packages/
    mv /var/lib/mock/${MOCK_CONF}/result/*.rpm ${OUTPUT_DIR}/${LIST_NAME}/os/Packages/
    #ln -f ${OUTPUT_DIR}/${LIST_NAME}/source/Packages/*.rpm ${LOCAL_REPO_DIR}/source/${LIST_NAME}-SRPMS/
    #createrepo --update ${LOCAL_REPO_DIR}/source/
    # createrepo --update -g local-build-comps.xml ${LOCAL_REPO_DIR}/
    createrepo --update ${LOCAL_REPO_DIR}/
  else
    echo "  FAILURE"
    echo "    Unable to build: ${package}"
    echo "    Unable to build: ${package}" >> ${WORK_LOG}
    exit 5    
  fi
