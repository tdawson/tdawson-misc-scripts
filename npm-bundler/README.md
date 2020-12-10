# npm bundler
Downloads the npm tarball for a npm module.
Then downloads the prod (runtime) modules for it, in node_modules_prod
Then downloads the dev (build-time) modules for it, in node_modules_dev
It then tars up the two directories, into seperate tarballs.
All three tarballs are copied to the users rpmbuild Source directory.

## How to run
 ./npm-bundler.sh <npm_name> [version]


## Usage in a rpm spec file
Currently, this is how you use this in a rpm spec file.

> ...
> License:  <license1> and <license2> and <license3>
> ...
> Source1:       %{npm_name}-%{version}-nm-prod.tgz
> Source2:       %{npm_name}-%{version}-nm-dev.tgz
> ...
> %install
> ...
> # Setup bundled node modules
> tar xfz %{SOURCE1}
> mkdir -p node_modules
> pushd node_modules
> ln -s ../node_modules_prod/* .
> ln -s ../node_modules_prod/.bin .
> popd
> cp -pr node_modules node_modules_prod %{buildroot}%{nodejs_sitelib}/%{npm_name}
> ...
> %check
> %nodejs_symlink_deps --check
> %if 0%{?enable_tests}
> tar xfz %{SOURCE2}
> pushd node_modules
> ln -s ../node_modules_dev/* .
> popd
> pushd node_modules/.bin
> ln -s ../../node_modules_dev/.bin/* .
> popd
> # Example test run using the binary in ./node_modules/.bin/
> ./node_modules/.bin/vows --spec --isolate
> %endif
> ...


