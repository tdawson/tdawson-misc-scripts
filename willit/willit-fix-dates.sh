#!/bin/bash
#
# Run this script after you have ran willit.py once
#   Then run willit-fix-dates.py
#

export REPOLIST="epel7 epel8 epel9 epel8-next epel9-next"

# Get all the data from koji
for repo in $REPOLIST
do
  echo "$repo"
  koji list-history --tag=$repo >> $repo.full-history
done

# Get just the tagged in lines
for repo in $REPOLIST
do
  echo "$repo"
  grep "tagged into epel" $repo.full-history >> $repo.full-tagged
done

# Convert into "date snvr" and "date rpmname"
for repo in $REPOLIST
do
  echo
  echo "$repo"
  cat $repo.full-tagged | while read line
  do
    old_date=$(echo "$line" | awk '{print $1 " " $2 " " $3 " " $4 " " $5}')
    new_date=$(date --date="$old_date" +%Y-%m-%d)
    pkg_name=$(echo "$line" | awk '{print $6}' | rev | cut -d'-' -f3- | rev)
    pkg_nvr=$(echo "$line" | awk '{print $6}')
    echo "$new_date $pkg_name" >> $repo.full-date-sname
    echo "$new_date $pkg_nvr" >> $repo.full-date-snvr
    echo -n "."
  done
  sort -o $repo.full-date-sname $repo.full-date-sname
  sort -o $repo.full-date-snvr $repo.full-date-snvr
  echo
done

# Trimm date-sname to just the first ones
# Generate NEW packages per day
for repo in $REPOLIST
do
  echo
  echo "$repo"
  rm -f $repo.cache $repo.trim-date-sname
  touch $repo.cache $repo.trim-date-sname
  cat $repo.full-date-sname | while read line
  do
    pkg=$(echo "$line" | awk '{print $2}')
    if ! grep -q "^$pkg$" $repo.cache ; then
        echo "$line" >> $repo.trim-date-sname
        echo "$pkg" >> $repo.cache
    fi
  done
done

# After this is done, then make sure your repolist is setup on
#  willit-fix-dates.py before running it.
# ./willit-fix-dates.py
