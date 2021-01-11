#!/bin/bash
OUTPUT_DIR="${HOME}/rpmbuild/SOURCES"

usage() {
  echo "Usage `basename $0` <npm_name> [version] " >&2
  echo >&2
  echo "  Given a npm module name, and optionally a version," >&2
  echo "    download the npm, the prod and dev dependencies," >&2
  echo "    each in their own tarball." >&2
  echo "    Also finds licenses prod dependencies." >&2
  echo "  All three tarballs  and license list are copied to ${OUTPUT_DIR}" >&2
  echo >&2
  exit 1
}

if ! [ -f /usr/bin/npm ]; then 
  echo >&2
  echo "`basename $0` requires npm to run" >&2
  echo >&2
  echo "Run the following to fix this" >&2
  echo "  sudo dnf install npm" >&2
  echo >&2
  exit 2
fi 

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
mkdir -p ${OUTPUT_DIR}
mkdir -p ${TMP_DIR}
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
echo "LICENSES IN BUNDLE:"
find . -name "package.json" -exec jq .license {} \; >> ${TMP_DIR}/${PACKAGE}-${VERSION}-bundled-licenses.txt
find . -name "package.json" -exec jq '.licenses[] .type' {} \; >> ${TMP_DIR}/${PACKAGE}-${VERSION}-bundled-licenses.txt 2>/dev/null
sort -u -o ${TMP_DIR}/${PACKAGE}-${VERSION}-bundled-licenses.txt ${TMP_DIR}/${PACKAGE}-${VERSION}-bundled-licenses.txt
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
cp -v ${PACKAGE}-${VERSION}* $HOME/rpmbuild/SOURCES
popd > /dev/null
rm -rf ${TMP_DIR}
