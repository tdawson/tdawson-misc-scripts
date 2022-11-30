#! /usr/bin/bash

for repo in epel8 epel9
do
  echo ; echo ${repo}
  echo "  Gathering lists"
  koji -q list-tagged --latest ${repo} >> ${repo}.full
  koji -q list-tagged ${repo}-next >> ${repo}-next.full
  echo "  Processsing lists"
  cat ${repo}.full | awk '{print $1}' | sort -u -o ${repo}.nvr
  cat ${repo}-next.full | awk '{print $1}' | sort -u -o ${repo}-next.nvr
  cat ${repo}.nvr | while read line; do name=$(echo $line | rev | cut -d'-' -f3- | rev); vr=$(echo $line | rev | cut -d'-' -f1,2 | rev); echo "$name $line $vr" >> ${repo}.name-nvr-vr; done
  cat ${repo}-next.nvr | while read line; do name=$(echo $line | rev | cut -d'-' -f3- | rev); vr=$(echo $line | rev | cut -d'-' -f1,2 | rev); echo "$name $line $vr" >> ${repo}-next.name-nvr-vr; done
  echo "  Comparing lists"
  cat ${repo}-next.name-nvr-vr | while read line
    do
      next_name=$(echo "$line" | awk '{print $1}')
      if [ "${repo}" == "epel8" ] ; then
        next_vr=$(echo "$line" | awk '{print $3}' | sed 's/el8.next/el8/')
      else
        next_vr=$(echo "$line" | awk '{print $3}' | sed 's/el9.next/el9/')
      fi
      epel_vr=$(grep  "^$next_name " ${repo}.name-nvr-vr| tail -n1 | awk '{print $3}')
      # echo "$next_name NEXT: $next_vr  EPEL: $epel_vr"
      rpmdev-vercmp $next_vr $epel_vr >/dev/null 2>&1
      this_test=$?
      # echo "  $this_test"
      case $this_test in
        0 ) echo "$line EPEL: $epel_vr" >> comp.${repo}.same ;;
        11 ) echo "$line EPEL: $epel_vr" >> comp.${repo}.stream-newer ;;
        12 ) echo "$line EPEL: $epel_vr" >> comp.${repo}.epel-newer ;;
      esac
    done
    grep tdawson ${repo}-next.full | awk '{print $1}' | while read line
    do
      grep $line comp.${repo}.same | awk '{print $2}' >> untag.list.${repo}-next.same.tdawson
    done
    cat comp${repo}.epel-newer | awk '{print $2}' >> untag.list.${repo}-next.older.all
done

