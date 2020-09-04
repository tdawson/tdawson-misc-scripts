#!/bin/bash

usage() {
  echo "Usage `basename $0` <npm_name> [version] " >&2
  echo >&2
  echo "  Given a npm module name, and optionally a version," >&2
  echo "    download the npm, the prod and dev dependencies," >&2
  echo "    each in their own tarball." >&2
  echo "  All three tarballs are copied to $HOME/rpmbuild/SOURCES" >&2
  echo >&2
  exit 1
}

if [ $# -lt 1 ]; then 
  usage
else
  case $1 in
	  -h | --help )
		  usage
		;;
		* )
		  PACKAGE="$1"
		;;
	esac
fi 

if [ $# -ge 2 ]; then 
  VERSION="$2"
else
  VERSION="$(npm view ${PACKAGE} version)"
fi 

TMP_DIR=$(mktemp -d -t ci-XXXXXXXXXX)
mkdir ${TMP_DIR}
pushd ${TMP_DIR}
npm pack ${PACKAGE}
tar xfz *.tgz
cd package
echo " Downloading prod dependencies"
npm install --no-optional --only=prod
if [ $? -ge 1 ] ; then
  echo "    ERROR WILL ROBINSON"
	rm -rf node_modules
else
  echo "    Successful prod dependences download"
	mv node_modules/ node_modules_prod
fi
# FIND SOMEWHERE TO PUT LICENSES
# FOR NOW JUST PRINT THEM OUT
echo "LICENSES IN BUNDLE:"
find . -name "package.json" -exec jq .license {} \; | sort -u
echo " Downloading dev dependencies"
npm install --no-optional --only=dev
if [ $? -ge 1 ] ; then
  echo "    ERROR WILL ROBINSON"
else
  echo "    Successful dev dependences download"
	mv node_modules/ node_modules_dev
fi
if [ -d node_modules_prod ] ; then
  tar cfz ../${PACKAGE}-${VERSION}-nm-prod.tgz node_modules_prod
fi
if [ -d node_modules_dev ] ; then
  tar cfz ../${PACKAGE}-${VERSION}-nm-dev.tgz node_modules_dev
fi
cd ..
cp ${PACKAGE}-${VERSION}* $HOME/rpmbuild/SOURCES
popd > /dev/null
rm -rf ${TMP_DIR}
