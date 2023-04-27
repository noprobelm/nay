import concurrent.futures
import os
import re
import shlex
import shutil
import subprocess
from typing import Optional

import networkx as nx
import requests
from rich.console import Group
from rich.table import Column, Table
from rich.text import Text

from .config import CACHEDIR
from .console import console
from .db import DATABASES, INSTALLED, SYNC_PACKAGES
from .package import AURPackage, Package, SyncPackage

SORT_PRIORITIES = {"db": {"core": 0, "extra": 1, "community": 2, "multilib": 4}}
for num, db in enumerate(DATABASES):
    num += max([num for num in SORT_PRIORITIES["db"].values()])
    if db not in SORT_PRIORITIES["db"].keys():
        SORT_PRIORITIES["db"][db] = num
SORT_PRIORITIES["db"]["aur"] = max([num for num in SORT_PRIORITIES["db"].values()])


def refresh() -> None:
    """
    Refresh the sync database. This is a pure pacman wrapper
    """
    subprocess.run(shlex.split("sudo pacman -Sy"))


def force_refresh() -> None:
    """
    Force refresh the sync database. This is a pure pacman wrapper.
    """
    subprocess.run(shlex.split("sudo pacman -Syy"))


def upgrade() -> None:
    """Upgrade all system packages"""
    subprocess.run(shlex.split("sudo pacman -Su"))


def clean() -> None:
    """Clean up unused package cache data"""
    subprocess.run(shlex.split("sudo pacman -Sc"))
    response = console.input(
        "\n[bright_blue]::[/bright_blue] Do you want to remove all other AUR packages from cache? [Y/n] "
    )

    if response.lower() == "y":
        console.print("removing AUR packages from cache...")
        os.chdir(CACHEDIR)
        for obj in os.listdir():
            shutil.rmtree(obj, ignore_errors=True)
    response = console.input(
        "\n[bright_blue]::[/bright_blue] Do you want to remove ALL untracked AUR files? [Y/n] "
    )

    if response.lower() == "y":
        console.print("removing untracked AUR files from cache...")
        os.chdir(CACHEDIR)
        for obj in os.listdir():
            if os.path.isdir(os.path.join(os.getcwd(), obj)):
                os.chdir(os.path.join(os.getcwd(), obj))
                for _ in os.listdir():
                    if _.endswith(".tar.zst"):
                        os.remove(_)
                os.chdir("../")


def query_local(query: Optional[str] = "") -> None:
    """
    Query the local sync database. This is a pure pacman wrapper

    :param force: Optional parameter indicating whether the sync database should be refreshed even if it's flagged as up-to-date (not generally recommended). Default is False
    :type force: Optional[bool]

    """
    subprocess.run(shlex.split(f"pacman -Qs {query}"))


def get_pkgbuild(pkg: Package, pkgdir: Optional[str] = None) -> None:
    """
    Get the PKGBUILD file from package.Package data

    :param pkg: The package.Package object to get the PKGBUILD for
    :type pkg: package.Package
    :param pkgdir: Optional directory to clone the PKGBUILD to. Default is 'None'
    :type pkgdir: Optional[str]

    """

    if not pkgdir:
        pkgdir = os.getcwd()
    subprocess.run(
        shlex.split(
            f"git clone https://aur.archlinux.org/{pkg.name}.git {pkgdir}/{pkg.name}"
        ),
        capture_output=True,
    )


def makepkg(pkg: Package, pkgdir, flags: str) -> None:
    """
    Make a package using 'makepkg'. This is a pure pacman wrapper.

    :param pkg: The package.Package object to make the package from
    :type pkg: package.Package
    :param pkgdir: The full path (exclusive of the package path itself)
    :type pkgdir: str
    :param flags: The flags to pass to 'makepkg' (exlusive of the leading '-')
    :type flags: str

    """
    os.chdir(f"{pkgdir}/{pkg.name}")
    subprocess.run(shlex.split(f"makepkg -{flags}"))

    if clean is True:
        os.chdir("../")
        shutil.rmtree(f"{os.getcwd()}/{pkg.name}", ignore_errors=True)


def get_aur_tree(
    *packages: Package, multithread: bool = True, recursive: bool = True
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

    if multithread:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for pkg in packages:
                future = executor.submit(pkg.get_aur_dependency_tree)
                futures.append(future)
        for future in futures:
            tree = nx.compose(tree, future.result())
    else:
        for pkg in packages:
            pkg_tree = pkg.get_aur_dependency_tree
            tree = nx.compose(tree, pkg_tree)

    if recursive is False:
        return tree

    layers = [layer for layer in nx.bfs_layers(tree, packages)]
    if len(layers) > 1:
        dependencies = layers[0]
        tree = nx.compose(tree, get_aur_tree(*dependencies))

    else:
        return tree

    return tree


def install(*packages: Package, nodeps=False, nodeps_recursive=False) -> None:
    """
    Get the AUR tree for a package or series of packages

    :param packages: A package or series of package objects to install
    :type packages: package.Package

    """

    def get_sync_explicit() -> list[SyncPackage]:
        """
        Get the sync explicit targets

        :return: A list of the sync explicit packages
        :rtype: list[SyncPackage]
        """
        sync_explicit = [pkg for pkg in packages if isinstance(pkg, SyncPackage)]
        return sync_explicit

    def get_aur_explicit() -> list[AURPackage]:
        """
        Get the aur explicit targets

        :return: A list of the aur explicit packages
        :rtype: list[AurPackage]
        """

        aur_explicit = [pkg for pkg in packages if isinstance(pkg, AURPackage)]
        return aur_explicit

    def get_aur_depends(aur_tree: nx.DiGraph) -> list[AURPackage]:
        """
        Get the aur dependencies from installation targets

        :param aur_tree: The dependency tree of the AUR explicit packages
        :type aur_tree: nx.DiGraph

        :return: A list of the aur dependencies
        :rtype: list[AurPackage]
        """

        aur_depends = []
        for pkg, dep in aur_tree.edges:
            if dep.name not in INSTALLED and aur_tree.get_edge_data(pkg, dep)[
                "dtype"
            ] in [
                "check",
                "make",
                "depends",
            ]:
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
                if isinstance(depends, list):
                    sync_depends.extend(
                        [
                            dep
                            for dep in depends
                            if dep not in INSTALLED and dep in SYNC_PACKAGES
                        ]
                    )

        sync_depends = get_packages(*sync_depends)
        return sync_depends

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

    def preview_install(*packages: AURPackage) -> None:
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

    def resolve_dependencies(aur_tree: nx.DiGraph) -> nx.DiGraph:
        """
        Recursively resolve dependencies using nx.DiGraph as starting point

        :param aur_tree: A shallow (i.e. consisting only of explicit AUR targets and their immediate dependencies) networkx DiGraph to be recursively filled out
        :type aur_tree: nx.DiGraph

        :returns: A dependency tree of AUR explicit targets and all descendent dependencies
        :rtype: nx.DiGraph
        """
        aur_tree = nx.compose(aur_tree, get_aur_tree(*aur_depends))
        return aur_tree

    def get_missing_pkgbuild(
        *packages: AURPackage, multithread=True, verbose=False
    ) -> None:
        """
        Get missing PKGBUILD files

        :param packages: An AURPackage or series of AURPackage objects to get PKGBUILD data for
        :type packages: AURPackage
        :param multithread: Optional parameter indicating whether this function should be multithreaded. Default is True
        :type multithread: Optional[bool]
        :param verbose: Optional parameter indicating whether success/failure messages should be verbose. Default is False
        :type verbose: Optional[bool]
        """
        missing = []
        for pkg in packages:
            if not pkg.pkgbuild_exists:
                missing.append(pkg)
            else:
                if verbose:
                    console.print(
                        f"[notify]::[/notify] PKGBUILD up to date, skipping download: [notify]{pkg.name}"
                    )

        if multithread:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                for num, pkg in enumerate(missing):
                    executor.submit(get_pkgbuild, pkg, CACHEDIR)
                    if verbose:
                        console.print(
                            f"[notify]::[/notify] ({num+1}/{len(missing)}) Downloaded PKGBUILD: [notify]{pkg.name}"
                        )
        else:
            for num, pkg in enumerate(missing):
                get_pkgbuild(pkg, CACHEDIR)
                if verbose:
                    console.print(
                        f"[notify]::[/notify] {num+1}/{len(missing)} Downloaded PKGBUILD: [notify]{pkg.name}"
                    )

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
        for num, layer in enumerate(layers):
            targets = []
            for pkg in layer:
                if nodeps_recursive is True:
                    makepkg(pkg, CACHEDIR, "fscd")
                elif nodeps is True and num + 1 == len(layers):
                    makepkg(pkg, CACHEDIR, "fscd")
                else:
                    makepkg(pkg, CACHEDIR, "fsc")
                pattern = f"{pkg.name}-{pkg.version}-"
                for obj in os.listdir(os.path.join(CACHEDIR, pkg.name)):
                    if pattern in obj and obj.endswith("zst"):
                        targets.append(os.path.join(CACHEDIR, pkg.name, obj))

            subprocess.run(shlex.split(f"sudo pacman -U {' '.join(targets)}"))

    def install_sync() -> None:
        """Install explicit sync packages"""
        subprocess.run(
            shlex.split(f"sudo pacman -S {[pkg.name for pkg in sync_explicit]}")
        )

    sync_explicit = get_sync_explicit()
    aur_explicit = get_aur_explicit()
    aur_tree = get_aur_tree(*aur_explicit, recursive=False)
    aur_depends = get_aur_depends(aur_tree)
    sync_depends = get_sync_depends(*aur_explicit)
    aur = aur_explicit + aur_depends

    preview_job(
        sync_explicit=sync_explicit,
        aur_explicit=aur_explicit,
        aur_depends=aur_depends,
        sync_depends=sync_depends,
    )
    get_missing_pkgbuild(*aur, verbose=True)
    preview_install(*aur)
    prompt_proceed()
    aur_tree = resolve_dependencies(aur_tree)

    remaining_deps = [pkg for pkg in aur_tree if pkg not in aur]
    get_missing_pkgbuild(*remaining_deps, verbose=False)

    if aur_tree:
        install_aur(aur_tree)
    if sync_explicit:
        install_sync()


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
        AURPackage.from_search_query(result) for result in aur_query["results"]
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


def get_packages(*pkg_names: str) -> list[Package]:
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
        if name in SYNC_PACKAGES:
            for database in DATABASES:
                pkg = DATABASES[database].get_pkg(name)
                if pkg:
                    pkg = SyncPackage.from_pyalpm(pkg)
                    packages.append(pkg)
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
    render_result = []
    if include_num is True:
        for num in packages:
            renderable = Text(f"{num} ")
            renderable.stylize("magenta", 0, len(renderable))
            renderable.append_text(packages[num].renderable)
            render_result.append(renderable)
    else:
        render_result = [packages[pkg].renderable for pkg in packages]

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
