# build-order-sort.sh
Given a list of source packages, finds all the build dependencies and
then sorts them into the order they should be built.

If there is a circular dependency, among the list of packages, it will
stop itself and say "SOMETHING IS WRONG"  If that happens, it is up to
you to determine the circular dependency.  It is best to start looking at
the dependencies for the packages on the layer that first says something
is wrong.

## Examples:
* build-order-sort.sh -v --no-order kde.list
** This gets the dependencies, and clears the build order
* build-order-sort.sh --no-new-deps --no-new-order kde.list
** The attempts to set the build order
* # Fix the first batch of circular dependencies
* build-order-sort.sh --no-new-deps kde.list
** Clear out the build order, and attempts to set the build orders.

