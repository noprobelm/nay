import os
import re
import shlex
import shutil
import subprocess
from typing import Optional

import threading
import time
from concurrent.futures import ThreadPoolExecutor
import networkx as nx
import requests
from rich.console import Group
from rich.table import Column, Table
from rich.text import Text

from .config import CACHEDIR
from .console import console
from .db import DATABASES, SYNC_PACKAGES
from .package import AURPackage, SyncPackage

SRCDIR = os.getcwd()
SORT_PRIORITIES = {"db": {"core": 0, "extra": 1, "community": 2, "multilib": 4}}
for num, db in enumerate(DATABASES):
    num += max([num for num in SORT_PRIORITIES["db"].values()])
    if db not in SORT_PRIORITIES["db"].keys():
        SORT_PRIORITIES["db"][db] = num
SORT_PRIORITIES["db"]["aur"] = max([num for num in SORT_PRIORITIES["db"].values()])


def refresh(force: Optional[bool] = False):
    """Refresh the sync databases"""

    if force:
        subprocess.run(shlex.split(f"sudo pacman -Syy"))
    else:
        subprocess.run(shlex.split(f"sudo pacman -Sy"))


def upgrade(force_refresh: Optional[bool] = False):
    """Upgrade all system packages"""
    subprocess.run(shlex.split("sudo pacman -Su"))


def clean():
    """Clean up unused package cache data"""
    subprocess.run(shlex.split(f"sudo pacman -Sc"))
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

    os.chdir(SRCDIR)


def query_local(query: Optional[str] = ""):
    subprocess.run(shlex.split(f"pacman -Qs {query}"))


def get_pkgbuild(pkg, clonedir: Optional[str] = None) -> None:
    """Get the PKGBUILD file from package.Package data"""
    if not clonedir:
        clonedir = os.getcwd()
    subprocess.run(
        shlex.split(
            f"git clone https://aur.archlinux.org/{pkg.name}.git {clonedir}/{pkg.name}"
        ),
        capture_output=True,
    )


def makepkg(pkg, clonedir, flags: str, clean: Optional[bool] = False):
    """Run makepkg on a PKGBUILD"""
    os.chdir(f"{clonedir}/{pkg.name}")
    subprocess.run(shlex.split(f"makepkg -{flags}"))

    if clean == True:
        os.chdir("../")
        shutil.rmtree(f"{os.getcwd()}/{pkg.name}", ignore_errors=True)


def get_aur_tree(*packages, multithread=False, recursive=True):
    tree = nx.DiGraph()
    for pkg in packages:
        tree = nx.compose(tree, pkg.aur_dependency_tree)

    if recursive == False:
        return tree

    layers = [layer for layer in nx.bfs_layers(tree, packages)]
    if len(layers) > 1:
        dependencies = layers[0]
        tree = nx.compose(tree, get_aur_tree(*dependencies))
    else:
        return tree

    return tree


def install(*packages):
    """Install a package based on package.Package data"""

    def get_sync_explicit():
        sync_explicit = [pkg for pkg in packages if isinstance(pkg, SyncPackage)]
        return sync_explicit

    def get_aur_explicit():
        aur_explicit = [pkg for pkg in packages if isinstance(pkg, AURPackage)]
        return aur_explicit

    def preview_job(sync_explicit=None, aur_explicit=None, aur_depends=None):
        if sync_explicit:
            output = [f"{pkg.name}-{pkg.version}" for pkg in sync_explicit]
            console.print(
                f"Sync Explicit {len(sync_explicit)}: {', '.join([pkg for pkg in output])}"
            )
        if aur_explicit:
            output = [f"{pkg.name}-{pkg.version}" for pkg in aur_explicit]
            console.print(
                f"AUR Explicit {len(aur_explicit)}: {', '.join([pkg for pkg in output])}"
            )

        if aur_depends:
            output = [f"{pkg.name}-{pkg.version}" for pkg in aur_depends]
            console.print(
                f"AUR Dependency ({len(aur_depends)}): {', '.join([out for out in output])}"
            )

    def preview_install(*packages):
        install_preview = Table.grid(
            Column("num", justify="right"),
            Column("pkgname", width=50, justify="left"),
            Column("pkgbuild_exists"),
            padding=(0, 1, 0, 1),
        )

        for num, pkg in enumerate(packages):
            # TODO: Fix hardcoded "Build Files Exist" -- I'm not how we'd encounter a scenario where we got here and they don't already exist
            install_preview.add_row(
                str(len(packages) - num), pkg.name, "Build Files Exist"
            )

        console.print(install_preview)

    def prompt_proceed():
        prompt = console.input(
            "[bright_green]==>[/bright_green] Install packages? [Y/n] "
        )
        if not prompt.lower().startswith("y"):
            quit()

    def resolve_dependencies(aur_tree):
        aur_tree = nx.compose(aur_tree, get_aur_tree(*aur_depends))
        return aur_tree

    def get_missing_pkgbuild(*packages, verbose=False):
        missing = []
        for pkg in packages:
            if not pkg.pkgbuild_exists:
                missing.append(pkg)
            else:
                if verbose:
                    console.print(
                        f":: PKGBUILD up to date, skipping download: {pkg.name}"
                    )

        for num, pkg in enumerate(missing):
            get_pkgbuild(pkg, CACHEDIR)
            if verbose:
                console.print(
                    f":: {num+1}/{len(missing)} Downloaded PKGBUILD: {pkg.name}"
                )

    def install_aur(aur_tree):
        layers = [layer for layer in nx.bfs_layers(aur_tree, aur_explicit)][::-1]
        for layer in layers:
            targets = []
            for pkg in layer:
                makepkg(pkg, CACHEDIR, "fsc")
                pattern = f"{pkg.name}-{pkg.version}-"
                for obj in os.listdir(os.path.join(CACHEDIR, pkg.name)):
                    if pattern in obj and obj.endswith("zst"):
                        targets.append(os.path.join(CACHEDIR, pkg.name, obj))

            subprocess.run(shlex.split(f"sudo pacman -U {' '.join(targets)}"))

    def install_sync():
        subprocess.run(
            shlex.split(f"sudo pacman -S {[pkg.name for pkg in sync_explicit]}")
        )

    sync_explicit = get_sync_explicit()
    aur_explicit = get_aur_explicit()
    aur_tree = get_aur_tree(*aur_explicit, recursive=False)
    aur_depends = []
    for pkg, dep in aur_tree.edges:
        if aur_tree.get_edge_data(pkg, dep)["dtype"] in [
            "check",
            "make",
            "depends",
        ]:
            aur_depends.append(dep)

    aur = aur_explicit + aur_depends

    preview_job(sync_explicit, aur_explicit, aur_depends)
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


def search(query: str, sortby: Optional[str] = "db"):
    """Query the sync databases and AUR"""
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


def get_packages(*pkg_names):
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


def print_pkglist(packages, include_num: Optional[bool] = False):
    render_result = []
    if include_num == True:
        for num in packages:
            renderable = Text(f"{num} ")
            renderable.stylize("magenta", 0, len(renderable))
            renderable.append_text(packages[num].renderable)
            render_result.append(renderable)
    else:
        render_result = [packages[pkg].renderable for pkg in packages]

    render_result = Group(*render_result)

    console.print(render_result)


def print_pkginfo(packages):
    aur = []
    sync = []
    for pkg in packages:
        if pkg.db == "aur":
            aur.append(pkg.info)
        else:
            sync.append(pkg)

    aur = Group(*aur)

    if sync:
        subprocess.run(
            shlex.split(f"pacman -Si {' '.join([pkg.name for pkg in sync])}")
        )

    console.print(aur)


def select_packages(packages):
    """Selects a package or packages based on user promopt to TTY"""

    # TODO: Add functionality for excluding packages (e.g. ^4)

    console.print(
        "[bright_green]==>[/bright_green] Packages to install (eg: 1 2 3, 1-3 or ^4)"
    )
    selections = console.input("[bright_green]==>[/bright_green] ")

    matches = re.findall(r"\d+(?:-\d+)?", selections)
    selections = set()
    for match in matches:
        if "-" in match:
            start, end = match.split("-")
            for num in range(int(start), int(end) + 1):
                selections.add(num)
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

    selected = [AURPackage.from_info_query(result) for result in aur_query["results"]]

    return selected
