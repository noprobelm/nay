import configparser
import re
import os
import subprocess
import shlex

import pyalpm
from pyalpm import Handle
from .console import console, default
from rich.console import Group
from typing import Optional, Union
from .package import Package, AURPackage, AURBasic, SyncPackage
import networkx as nx
import requests
from rich.text import Text
from rich.table import Table, Column
from .utils import makepkg
from .config import CACHEDIR

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
            sync_depends.extend(
                [SYNC_PACKAGES[dep] for dep in depends if dep in SYNC_PACKAGES.keys()]
            )

    return sync_depends


def install(
    *packages: Package,
    skip_verchecks: Optional[bool] = False,
    skip_depchecks: Optional[bool] = False,
    download_only: Optional[bool] = False,
) -> None:
    """
    Get the AUR tree for a package or series of packages

    :param packages: A package or series of package objects to install
    :type packages: package.Package
    :param skip_verchecks: Optional option to skip version checks for dependencies. Default is False
    :type skip_verchecks: Optinoal[bool]=False
    :param skip_depchecks: Optional option to skip all dependency checks. Default is False
    :type skip_depchecks: Optinoal[bool]=False

    """

    def preview_job(
        sync_explicit: Optional[list[SyncPackage]] = None,
        sync_depends: Optional[list[SyncPackage]] = None,
        aur_explicit: Optional[list[AURPackage]] = None,
        aur_depends: Optional[list[AURPackage]] = None,
    ) -> None:

        """
        Print a list of packages to be installed to the terminal

        :param sync_explicit: A list of SyncPackage objects to be explicitly installed
        :type sync_explicit: list[SyncPackage]
        :param sync_depends: A list of SyncPackage dependencies to be installed
        :type sync_depends: list[SyncPackage]
        :param aur_explicit: An list of AURPackage objects to be explicitly installed
        :type aur_explicit: list[AURPackage]
        :param aur_depends: A list of AURPackage dependencies to be installed
        :type aur_depends: list[AURPackage]
        """

        if sync_explicit:
            output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in sync_explicit]
            console.print(
                f"Sync Explicit {len(sync_explicit)}: {', '.join([pkg for pkg in output])}"
            )
        if aur_explicit:
            output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in aur_explicit]
            console.print(
                f"AUR Explicit ({len(aur_explicit)}): {', '.join([pkg for pkg in output])}"
            )

        if aur_depends:
            output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in aur_depends]
            console.print(
                f"AUR Dependency ({len(aur_depends)}): {', '.join([out for out in output])}"
            )

        if sync_depends:
            output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in sync_depends]
            console.print(
                f"Sync Dependency ({len(sync_depends)}): {', '.join([out for out in output])}"
            )

    def preview_aur(*packages: AURPackage) -> None:
        """
        Print an overview of the explicit and depends AUR packages to be installed

        :param packages: A package or series of AURPackage objects to be explicitly installed
        :type packages: package.AURPackage
        """

        install_preview = Table.grid(
            Column("num", justify="right"),
            Column("pkgname", width=35, justify="left"),
            Column("pkgbuild_exists"),
            padding=(0, 1, 0, 1),
        )

        for num, pkg in enumerate(packages):
            # TODO: Fix hardcoded "Build Files Exist" -- I'm not how we'd encounter a scenario where we got here and they don't already exist
            install_preview.add_row(
                f"[magenta]{len(packages) - num}[/magenta]",
                pkg.name,
                "[bright_green](Build Files Exist)",
            )

        console.print(install_preview)

    def prompt_proceed() -> None:
        """Present prompt to proceed with installation"""
        prompt = console.input(
            "[bright_green]==>[/bright_green] Install packages? [Y/n] "
        )
        if not prompt.lower().startswith("y"):
            quit()

    def install_aur(aur_tree: nx.DiGraph) -> None:
        """
        Install AUR targets according to their location in the hierarchy:

        - A breadth-first layer search is conducted and reversed to separate the ordered 'tiers' `makepkg` and `pacman -U` need to be executed in in order to result in successful makepkg for successors
        - Each layer is iterated through. For each package in a layer:
          - makepkg 'f' (force makepkg in the event package data already exists) 's' (install missing sync dependencies) 'c' (clean up unecessary data after makepkg finishes)
          - Match the filename pattern for the resulting package's tarball archive (i.e. '<pkgname>-<pkgver>-<architecture>.pkg.tar.zst) and append full path to installation targets
        - After all packages in a layer have been iterated and operated on, batch install using pacman -U
        - Repeat for each layer until all packages have been installed
        """
        layers = [layer for layer in nx.bfs_layers(aur_tree, aur_explicit)][::-1]
        for layer in layers:
            targets = []
            for pkg in layer:
                if skip_depchecks is True:
                    makepkg(pkg, CACHEDIR, "fscd")
                else:
                    makepkg(pkg, CACHEDIR, "fsc")
                pattern = f"{pkg.name}-"
                for obj in os.listdir(os.path.join(CACHEDIR, pkg.name)):
                    if pattern in obj and obj.endswith("zst"):
                        targets.append(os.path.join(CACHEDIR, pkg.name, obj))

            if download_only is False:
                subprocess.run(shlex.split(f"sudo pacman -U {' '.join(targets)}"))
            else:
                console.print(
                    f"-> nothing to install for {' '.join([target for target in targets])}"
                )

    def install_sync() -> None:
        """Install explicit sync packages"""
        flags = ""
        if skip_verchecks is True:
            flags = f"{flags}d"
            subprocess.run(
                shlex.split(
                    f"sudo pacman -Sd {' '.join([pkg.name for pkg in sync_explicit])}"
                )
            )
        elif skip_depchecks is True:
            flags = f"{flags}dd"
            subprocess.run(
                shlex.split(
                    f"sudo pacman -Sdd {' '.join([pkg.name for pkg in sync_explicit])}"
                )
            )
        if download_only is True:
            flags = f"{flags}w"

        subprocess.run(
            shlex.split(
                f"sudo pacman -S{flags} {' '.join([pkg.name for pkg in sync_explicit])}"
            )
        )

    sync_explicit = [pkg for pkg in packages if isinstance(pkg, SyncPackage)]
    aur_explicit = [pkg for pkg in packages if isinstance(pkg, AURPackage)]

    if skip_depchecks is True:
        preview_job(sync_explicit=sync_explicit, aur_explicit=aur_explicit)
        utils.get_missing_pkgbuild(*aur_explicit, verbose=True)
        if aur_explicit:
            preview_aur(*aur_explicit)
            prompt_proceed()
            aur_tree = nx.DiGraph()
            for pkg in aur_explicit:
                aur_tree.add_node(pkg)
            install_aur(aur_tree)

        if sync_explicit:
            install_sync()
        quit()

    aur_tree = get_dependency_tree(*aur_explicit, recursive=False)
    aur_depends = get_aur_depends(aur_tree)
    sync_depends = get_sync_depends(*aur_explicit)
    aur = aur_explicit + aur_depends

    preview_job(
        sync_explicit=sync_explicit,
        aur_explicit=aur_explicit,
        aur_depends=aur_depends,
        sync_depends=sync_depends,
    )
    get_missing_pkgbuild(*[pkg for pkg in aur], verbose=True)
    preview_aur(*aur)
    prompt_proceed()
    if aur_depends:
        aur_tree = nx.compose(aur_tree, get_dependency_tree(*aur_depends))

    remaining_deps = [pkg for pkg in aur_tree if pkg not in aur]
    get_missing_pkgbuild(*remaining_deps, verbose=False)

    if aur_tree:
        install_aur(aur_tree)
    if sync_explicit:
        install_sync()


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
        return Text(f"(Orphaned) ", style="bright_red") if pkg.orphaned else Text("")

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