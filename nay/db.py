import configparser
from typing import Optional, Union

import networkx as nx
import pyalpm
import requests
from pyalpm import Handle

from .console import console
from .package import AURBasic, AURPackage, Package, SyncPackage

parser = configparser.ConfigParser(allow_no_value=True)
parser.read("/etc/pacman.conf")

handle = Handle("/", "/var/lib/pacman")
DATABASES = {
    db: handle.register_syncdb(db, pyalpm.SIG_DATABASE_OPTIONAL)
    for db in parser.sections()[1:]
}

SYNC_PACKAGES = {}
for db in DATABASES:
    SYNC_PACKAGES.update(
        {pkg.name: SyncPackage.from_pyalpm(pkg) for pkg in DATABASES[db].pkgcache}
    )

INSTALLED = {
    pkg.name: SyncPackage.from_pyalpm(pkg) for pkg in handle.get_localdb().pkgcache
}

SORT_PRIORITIES = {"db": {"core": 0, "extra": 1, "community": 2, "multilib": 4}}
for num, db in enumerate(DATABASES):
    num += max([num for num in SORT_PRIORITIES["db"].values()])
    if db not in SORT_PRIORITIES["db"].keys():
        SORT_PRIORITIES["db"][db] = num
SORT_PRIORITIES["db"]["aur"] = max([num for num in SORT_PRIORITIES["db"].values()])


def search(query: str, sortby: Optional[str] = "db") -> dict[int, Package]:
    """
    Query the sync databases and AUR. Exact matches will always be presented first despite specified sort order

    :param query: The search query to use
    :type query: str
    :param sortby: The package.Package attribute to sort results by

    :returns: A dictionary of integers representing index to package results
    :rtype: dict[int, Package]
    """
    packages = []

    for database in DATABASES:
        packages.extend(
            [SyncPackage.from_pyalpm(pkg) for pkg in DATABASES[database].search(query)]
        )

    aur_query = requests.get(
        f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={query}"
    ).json()

    packages.extend(
        AURBasic.from_search_query(result) for result in aur_query["results"]
    )
    packages = list(
        reversed(
            sorted(
                packages, key=lambda val: SORT_PRIORITIES[sortby][getattr(val, sortby)]
            )
        )
    )

    for num, pkg in enumerate(packages):
        if pkg.name == query:
            packages.append(packages.pop(num))

    packages = {len(packages) - num: pkg for num, pkg in enumerate(packages)}

    return packages


def get_packages(*pkg_names: str, verbose=True) -> list[Union[SyncPackage, AURPackage]]:
    """
    Get packages based on passed string or strings. Invalid results are ignored/dropped from return result.

    :param pkg_names: A string or series of strings for which SyncPackage or AURPackage objects will be fetched
    :type pkg_names: str

    :returns: Package list based on input
    :rtype: list[Package]
    """
    pkg_names = set(pkg_names)
    packages = []
    aur_search = []
    for name in pkg_names:
        if name in SYNC_PACKAGES.keys():
            packages.append(SYNC_PACKAGES[name])
        else:
            aur_search.append(name)

    if aur_search:
        aur_query = requests.get(
            f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join(aur_search)}"
        ).json()
        if aur_query:
            for result in aur_query["results"]:
                packages.append(AURPackage.from_info_query(result))
                aur_search = list(filter(lambda x: x != result["Name"], aur_search))

    if aur_search:
        console.print(f"[red]->[/red] No AUR package found for {', '.join(aur_search)}")

    return packages


def get_dependency_tree(
    *packages: Package,
    recursive: Optional[bool] = True,
    include_sync: Optional[bool] = False,
) -> nx.DiGraph:
    """
    Get the AUR tree for a package or series of packages

    :param multithread: Optional parameter indicating whether this function should be multithreaded. Default is True
    :type multithread: Optional[bool]
    :param recursive: Optional parameter indicating whether this function should run recursively. If 'False', only immediate dependencies will be returned. Defaults is True
    :type recursive: Optional[bool]

    :return: A dependency tree of all packages passed to the function
    :rtype: nx.DiGraph
    """
    tree = nx.DiGraph()
    aur_query = []

    aur_deps = {pkg: {} for pkg in packages}
    for pkg in packages:
        tree.add_node(pkg)
        for dtype in ["check_depends", "make_depends", "depends"]:
            for dep in getattr(pkg, dtype):
                if dep not in SYNC_PACKAGES.keys():
                    aur_query.append(dep)
                    aur_deps[pkg][dep] = {"dtype": dtype}

    aur_info = get_packages(*set(list(aur_query)), verbose=False)
    for pkg in aur_deps:
        for dep in aur_info:
            if dep.name in aur_deps[pkg].keys():
                tree.add_edge(pkg, dep, dtype=aur_deps[pkg][dep.name]["dtype"])
    if recursive is False:
        return tree

    layers = [layer for layer in nx.bfs_layers(tree, packages)]
    if len(layers) > 1:
        dependencies = layers[1]
        tree = nx.compose(tree, get_dependency_tree(*dependencies))

    return tree


def get_aur_depends(
    aur_tree: nx.DiGraph, skip_verchecks=False, skip_depchecks=False
) -> list[AURPackage]:
    """
    Get the aur dependencies from installation targets

    :param aur_tree: The dependency tree of the AUR explicit packages
    :type aur_tree: nx.DiGraph

    :return: A list of the aur dependencies
    :rtype: list[AurPackage]
    """

    aur_depends = []
    for pkg, dep in aur_tree.edges:
        if aur_tree.get_edge_data(pkg, dep)["dtype"] != "opt_depends":
            if dep.name not in INSTALLED.keys():
                aur_depends.append(dep)
            elif skip_verchecks is False:
                if INSTALLED[dep.name] != dep:
                    aur_depends.append(dep)

    return aur_depends


def get_sync_depends(*aur_explicit) -> list[SyncPackage]:
    """
    Get the sync dependencies from AUR explicit targets

    :param aur_explicit: An AURPackage or series of AURPackage objects
    :type aur_tree: package.AURPackage

    :return: A list of the aur dependencies
    :rtype: list[AurPackage]
    """

    sync_depends = []
    for pkg in aur_explicit:
        for dep_type in ["check_depends", "make_depends", "depends"]:
            depends = getattr(pkg, dep_type)
            for dep in depends:
                if dep in SYNC_PACKAGES.keys() and dep not in INSTALLED.keys():
                    sync_depends.append(SYNC_PACKAGES[dep])

    return sync_depends
