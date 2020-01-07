# Rebuild Package List

Rebuild packages, one at a time, adding the outputed pacakges to a repo.
It is expected that the build of the next package built will ustilize the updated repo.

This script is best when there are many packages that depend on the build before them.
But, it also is a simple, though slower, way to get a group of packages built.

## Different Scripts

At some point, these scripts may or may not be merged together, with just an option to do the various things.
As of this writting, they are all seperate scripts.

### rebuild-pkglist.sh

Reads a list of source package names.  Builds each package, one at a time.  If the build was successful, the outputed rpm's are added to a repo, and that repo is updated.  If the build was not successful, then the script stops.

This script is best when there are many packages that depend on the build before them.

### rebuild-nonstop-pkglist.sh

This is does the same things as regular rebuild-pkglist.sh, except that if a package does not build, it continues on.  It also does not wait for repo rebuilds to finish.

This is best for a bunch of packages that don't depend on each other.

### rebuild-pkglist-single.sh

rebuild-pkglist-single.sh <full path to src.rpm>

This does the same build, and repo updating, except that it builds whatever source rpm you give it.
