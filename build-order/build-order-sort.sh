#!/bin/bash
#
# Given a list of packages, find and list all the packages that 
#   need to be built, to build those packages.
#
#####
# VARIABLES
#####
DATAFILE=""
BUFFER=2
# COLOR VARIABLES
BROWN='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
# BINARY VARIABLES
VERBOSE="FALSE"
DO_DEPS="TRUE"
NEW_ORDER="TRUE"
DO_ORDER="TRUE"
# LIST VARIABLES
OLD_LIST=()
NEW_LIST=()



###############
# Show help
###############
usage() {
  echo "Usage `basename $0` <options> [filename] " >&2
  echo >&2
  echo "Given a  file with a list of packages, generated the" >&2
  echo "  build order based on dependencies." >&2
  echo >&2
  echo "Options:" >&2
  echo "  --no-new-deps" >&2
  echo "    Do not redo the deps" >&2
  echo "  --no-new-order" >&2
  echo "    Do not redo the order" >&2
  echo "  --no-order" >&2
  echo "    Do not update the order" >&2
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
    -f | --file )
      if [ -s ${2} ] ; then
        ORIGINAL_LIST+=("$(cat ${2})")
        shift
      else
        echo "${2} is not found, or empty"
	echo
        usage
        exit 2	
      fi
    ;;
    --no-new-deps)
      export DO_DEPS="FALSE"
    ;;
    --no-new-order)
      export NEW_ORDER="FALSE"
    ;;
    --no-order)
      export DO_ORDER="FALSE"
    ;;
    -v | --verbose | --debug)
      export VERBOSE="TRUE"
    ;;
    -h | --help )
      usage
      exit 2
    ;;
    * )
      if [ -s "${key}" ] ; then
        DATAFILE="${key}"
      else
        echo "ERROR: ${key} is not found, or empty"
	echo
        usage
        exit 2	
      fi
    ;;
  esac
  shift # past argument or value
done
if [ "${DATAFILE}" == "" ] ; then
  echo "NO PACKAGES LISTED"
  echo
  usage
  exit 5
fi

## Setup
if [ "${VERBOSE}" == "TRUE" ] ; then
  echo "SETUP"
fi
mkdir -p order deps
if [ "${DO_DEPS}" == "TRUE" ] ; then
  rm -f deps/*
fi
if [ "${NEW_ORDER}" == "TRUE" ] ; then
  rm -f order/*
fi
for package in $(cat ${DATAFILE})
do
  if [ "${VERBOSE}" == "TRUE" ] ; then
    echo "  ${package}"
  fi
  if [ "${DO_DEPS}" == "TRUE" ] ; then
    source_requires="$(dnf repoquery --srpm --qf="%{name}" --requires --resolve ${package} 2>/dev/null | grep -v 'Subscription Management')"
		if [ "${source_requires}" == "" ] ; then
		  touch deps/${package}
		else
		  # Find - the name of - the source rpms of - the packages needed to build - the source rpm of ${package}
		  dnf repoquery --srpm --qf="%{name}" list  $(dnf repoquery  --srpm --qf="%{sourcerpm}" --requires --resolve ${package} 2>/dev/null | grep -v 'Subscription Management' | sed "s/.src.rpm$//") 2>/dev/null | grep -v 'Subscription Management' >> deps/${package} 2>/dev/null
      # Find - the name of - the source rpms of - the packages needed to install - the packages needed to build - the source rpm of ${package}
		  dnf repoquery --srpm --qf="%{name}" list  $(dnf repoquery --qf="%{sourcerpm}" --requires --resolve ${source_requires} 2>/dev/null | grep -v 'Subscription Management' | sed "s/.src.rpm$//") 2>/dev/null | grep -v 'Subscription Management' >> deps/${package} 2>/dev/null
		  # sort and remove duplicates
		  sort -u -o deps/${package} deps/${package}
		fi
  fi
  if [ "${NEW_ORDER}" == "TRUE" ] ; then
    echo "${BUFFER}" >> order/${package}
  fi
done

if [ "${DO_ORDER}" == "TRUE" ] ; then
  #Get initial order numbers
  OLD_LIST+=("$(pushd order >/dev/null ; cat * | sort -n | uniq -c | awk '{print $2 ":" $1}';popd >/dev/null)")
  DO_LOOP="TRUE"
  OLD_EQUALS_NEW="FALSE"
  while [ "${DO_LOOP}" == "TRUE" ] 
  do
    echo "Doing a layer of ordering builds"
    # Do a layer of ordering
    for package in $(cat kde.list)
    do
      let this_order_num=$(cat order/$package)
      for build_source in $(cat deps/$package)
      do
        if grep -q ^${build_source}$ kde.list ; then
          let source_order_num=$(cat order/$build_source)
          if [ $this_order_num -le $source_order_num ] ; then
            let this_order_num=$source_order_num+2
            if [ "${VERBOSE}" == "TRUE" ] ; then
              echo "  $package $this_order_num"
            fi
          fi
        fi
      done
      echo $this_order_num > order/$package
    done
    NEW_LIST=()
    NEW_LIST+=("$(pushd order >/dev/null ; cat * | sort -n | uniq -c | awk '{print $2 ":" $1}'; popd   >/dev/null)")
    count=0
    OLD_EQUALS_NEW="TRUE"
    for new_line in ${NEW_LIST[@]}
    do
      line_number="$(echo ${new_line} | cut -d':' -f1)"
      old_line="${OLD_LIST[${count}]}"
      let count=$count+1
      let proper_line_number=$count*2
      if [ ${proper_line_number} -eq ${line_number} ] ; then
        if [ "${old_line}" == "${new_line}" ] ; then
          echo -e "${CYAN}${new_line}${NC}"
        else
          echo -e "${BROWN}${new_line} <-${CYAN}${old_line}${NC}"
          OLD_EQUALS_NEW="FALSE"
        fi
      else
        echo -e "${YELLOW}${new_line} - SOMETHING IS WRONG${NC}"
        DO_LOOP="FALSE"
        OLD_EQUALS_NEW="FALSE"
      fi
    done
    if [ "${OLD_EQUALS_NEW}" == "TRUE" ] ; then
      DO_LOOP="FALSE"
      echo "FINISHED"
    else
      OLD_LIST=()
      OLD_LIST+=(${NEW_LIST[@]})
    fi
  done
fi
