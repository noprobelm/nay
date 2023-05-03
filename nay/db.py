import configparser
import re
import shlex
import subprocess
from typing import Optional, Union

import networkx as nx
import pyalpm
import requests
from pyalpm import Handle
from rich.console import Group
from rich.text import Text

from .console import console, default
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


def get_packages(
    *pkg_names: str, verbose: Optional[bool] = False
) -> list[Union[SyncPackage, AURPackage]]:
    """
    Get packages based on passed string or strings. Invalid results are ignored/dropped from return result.

    :param pkg_names: A string or series of strings for which SyncPackage or AURPackage objects will be fetched
    :type pkg_names: str
    :param verbose: Flag to induce verbosity. Defaults to False
    :type verbose: bool


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

    if aur_search and verbose is True:
        console.print(f"[red]->[/red] No AUR package found for {', '.join(aur_search)}")

    return packages


def get_dependency_tree(
    *packages: Package,
    recursive: Optional[bool] = True,
) -> nx.DiGraph:
    """
    Get the AUR dependency tree for a package or series of packages

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

    aur_info = get_packages(*set(list(aur_query)))
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
    aur_tree: nx.DiGraph, skip_verchecks: Optional[bool] = False
) -> list[AURPackage]:
    """
    Get the aur dependencies from installation targets

    :param aur_tree: The dependency tree of the AUR explicit packages
    :type aur_tree: nx.DiGraph
    :param skip_verchecks: Flag to skip version checks for dependencies. Default is False
    :type skip_verchecks: bool

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


def print_pkglist(
    packages: dict[int, Package], include_num: Optional[bool] = False
) -> None:
    """
    Print a sequence of passed packages
    :param packages: A dictionary of integers representing index to package results
    :type packages: dict[int, Package]
    :param include_num: Optional bool to indicate whether a package's index should be included in the print result or not. Default is False
    :type include_num: Optional[bool]
    """

    def get_size(pkg):
        return Text(f"{pkg.size}")

    def get_isize(pkg):
        return Text(f"{pkg.isize}")

    def get_votes(pkg):
        return Text(f"{pkg.votes}")

    def get_popularity(pkg):
        return Text("{:.2f}".format(pkg.popularity))

    def get_orphan(pkg):
        return Text("(Orphaned) ", style="bright_red") if pkg.orphaned else Text("")

    def get_flag_date(pkg):
        return (
            Text(f"(Out-of-date): {pkg.flag_date.strftime('%Y-%m-%d')}")
            if pkg.flag_date
            else Text("")
        )

    render_result = []

    for num in packages:
        pkg = packages[num]

        renderable = Text.assemble(
            Text(
                pkg.db,
                style=pkg.db if pkg.db in default.styles.keys() else "other_db",
            ),
            Text("/"),
            Text(f"{pkg.name} "),
            Text(f"{pkg.version} ", style="cyan"),
        )

        if isinstance(pkg, SyncPackage):
            renderable.append_text(Text(f"({get_size(pkg)} "))
            renderable.append_text(Text(f"{get_isize(pkg)}) "))
            if pkg.name in INSTALLED.keys():
                renderable.append_text(
                    Text(
                        f"(Installed: {INSTALLED[pkg.name].version}) ",
                        style="bright_green",
                    )
                )

        elif isinstance(pkg, AURBasic):
            renderable.append_text(Text(f"(+{get_votes(pkg)} {get_popularity(pkg)}) "))
            if pkg.name in INSTALLED.keys():
                renderable.append_text(
                    Text(
                        f"(Installed: {INSTALLED[pkg.name].version}) ",
                        style="bright_green",
                    )
                )
            renderable.append_text(get_orphan(pkg))
            renderable.append_text(get_flag_date(pkg))

        if include_num is True:
            num = Text(f"{num} ")
            num.stylize("magenta", 0, len(num))
            num.append_text(renderable)
            renderable = num

        if pkg.desc:
            renderable = Text("\n    ").join([renderable, Text(pkg.desc)])

        render_result.append(renderable)

    render_result = Group(*render_result)

    console.print(render_result)


def print_pkginfo(*packages: Package) -> None:
    """
    Print a package's meta data according to pacman (sync packages) or AURweb RPC interface info request (AUR packages)
    :param packages: A package.Package or series of package.Package objects for which to retrieve info
    :type packages: package.Package
    """
    aur = []
    sync = []
    for pkg in packages:
        if isinstance(pkg, AURPackage):
            aur.append(pkg.info)
        else:
            sync.append(pkg)

    aur = Group(*aur)

    if sync:
        subprocess.run(
            shlex.split(f"pacman -Si {' '.join([pkg.name for pkg in sync])}")
        )

    console.print(aur)


def select_packages(packages: dict[int, Package]) -> list[Package]:
    """
    Select packages based on user input. Inputs can be separated by spaces
    Valid selections (any number of any combination of the below) * Must be separated by space characters:
      - int: A single selection (i.e. '1 3 5')
      - inclusive series of int: A range of selections to include (i.e. '1-3 6-9')
      - exclusive series of int: A range of selections to exclude (i.e. '^1-3 ^6-9')
    :param packages: A dictionary of integers representing index to package results
    :type packages: dict[int, Package]
    :returns: list of packages
    :rtype: list[Package]
    """

    # TODO: Add functionality for excluding packages (e.g. ^4)

    console.print(
        "[bright_green]==>[/bright_green] Packages to install (eg: 1 2 3, 1-3 or ^4)"
    )
    selections = console.input("[bright_green]==>[/bright_green] ")

    matches = re.findall(r"\^?\d+(?:-\d+)?", selections)
    selections = set()
    for match in matches:
        if "-" in match:
            start, end = match.split("-")
            if match.startswith("^"):
                start = start.strip("^")
                for num in range(int(start), int(end) + 1):
                    selections.discard(num)
            else:
                for num in range(int(start), int(end) + 1):
                    selections.add(num)
        elif match.startswith("^"):
            match = match.strip("^")
            selections.discard(int(match))
        else:
            selections.add(int(match))
    selected = []
    for num in selections:
        try:
            selected.append(packages[num])

        # Ignore invalid selections by the user
        except KeyError:
            pass

    aur_query = requests.get(
        f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join([pkg.name for pkg in selected])}"
    ).json()

    # Replace AUR packages generated from search query with AUR info query
    for result in aur_query["results"]:
        pkg = AURPackage.from_info_query(result)
        selected.pop(selected.index(pkg))
        selected.append(pkg)

    return selected
