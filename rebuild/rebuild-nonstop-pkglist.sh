#!/bin/bash
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
      # exit 3
    else
      echo "${package} $(rpm -qp --qf='%{name}-%{version}-%{release}' *.src.rpm) ${ALT_SOURCE_REPO}" >> ${WORK_LOG}
    fi
  else
    echo "${package} $(rpm -qp --qf='%{name}-%{version}-%{release}' *.src.rpm) ${SOURCE_REPO}" >> ${WORK_LOG}
  fi
  this_src_rpm="$(ls -1 *src.rpm)"
  # mock -r ${MOCK_CONF} --rebuild ${this_src_rpm}
  # mock -r ${MOCK_CONF} --no-clean --rebuild ${this_src_rpm}
  mock -r ${MOCK_CONF} --no-clean --rebuild ${this_src_rpm}
  if [ $? -eq 0 ] ; then
    echo "  SUCCESS: ${package}"
    echo "  SUCCESS: ${package}" >> ${WORK_LOG}
    
    mv ${this_src_rpm} ${DONE_DIR}
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
    # exit 5    
  fi
done
