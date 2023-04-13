import os
import shutil
import re
import requests
from typing import Optional
from .package import SyncDB, AUR
from .db import DATABASES
import subprocess
import shlex
from .console import console
from rich.console import Group
from rich.text import Text


SRCDIR = os.getcwd()

#####################################################################################################################################
#  ____                                   __        __                                 _____                 _   _                  #
# |  _ \ __ _  ___ _ __ ___   __ _ _ __   \ \      / / __ __ _ _ __  _ __   ___ _ __  |  ___|   _ _ __   ___| |_(_) ___  _ __  ___  #
# | |_) / _` |/ __| '_ ` _ \ / _` | '_ \   \ \ /\ / / '__/ _` | '_ \| '_ \ / _ \ '__| | |_ | | | | '_ \ / __| __| |/ _ \| '_ \/ __| #
# |  __/ (_| | (__| | | | | | (_| | | | |   \ V  V /| | | (_| | |_) | |_) |  __/ |    |  _|| |_| | | | | (__| |_| | (_) | | | \__ \ #
# |_|   \__,_|\___|_| |_| |_|\__,_|_| |_|    \_/\_/ |_|  \__,_| .__/| .__/ \___|_|    |_|   \__,_|_| |_|\___|\__|_|\___/|_| |_|___/ #
#                                                             |_|   |_|                                                             #
#####################################################################################################################################


def refresh(force: Optional[bool] = False):
    """Refresh the sync databases"""
    if force:
        subprocess.run(shlex.split(f"sudo pacman -Syy"))
    else:
        subprocess.run(shlex.split(f"sudo pacman -Sy"))


def upgrade(force_refresh: Optional[bool] = False):
    """Upgrade all system packages"""
    if force_refresh:
        subprocess.run(shlex.split("sudo pacman -Syyu"))
    else:
        subprocess.run(shlex.split("sudo pacman -Syu"))


def clean():
    """Clean up unused package cache data"""
    subprocess.run(shlex.split(f"pacman -Sc"))


def query_local(query: Optional[str] = ""):
    subprocess.run(shlex.split(f"pacman -Qs {query}"))


#############################################################################################################
#  _____      _                 _          _   _____                 _   _                   _ _ _          #
# | ____|_  _| |_ ___ _ __   __| | ___  __| | |  ___|   _ _ __   ___| |_(_) ___  _ __   __ _| (_) |_ _   _  #
# |  _| \ \/ / __/ _ \ '_ \ / _` |/ _ \/ _` | | |_ | | | | '_ \ / __| __| |/ _ \| '_ \ / _` | | | __| | | | #
# | |___ >  <| ||  __/ | | | (_| |  __/ (_| | |  _|| |_| | | | | (__| |_| | (_) | | | | (_| | | | |_| |_| | #
# |_____/_/\_\\__\___|_| |_|\__,_|\___|\__,_| |_|   \__,_|_| |_|\___|\__|_|\___/|_| |_|\__,_|_|_|\__|\__, | #
#                                                                                                    |___/  #
#############################################################################################################


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


def rm_pkgbuild(pkg, clonedir) -> None:
    shutil.rmtree(f"{clonedir}/{pkg.name}")


def makepkg(pkg, clonedir):
    """Run makepkg on a PKGBUILD"""
    os.chdir(f"{clonedir}/{pkg.name}")
    subprocess.run(shlex.split(f"makepkg -si"))
    os.chdir(SRCDIR)


def install(packages, clonedir: Optional[str] = "/tmp"):
    """Install a package based on package.Package data"""
    aur = [pkg for pkg in packages if pkg.db == "aur"]
    sync = [pkg for pkg in packages if pkg.db != "aur"]

    for pkg in aur:
        get_pkgbuild(pkg, clonedir)
        makepkg(pkg, clonedir)
        rm_pkgbuild(pkg, clonedir)

    subprocess.run(
        shlex.split(f"sudo pacman -S {' '.join([pkg.name for pkg in sync])}")
    )


def search(query: str):
    """Query the sync databases and AUR"""
    packages = []

    for database in DATABASES:
        packages.extend(
            [SyncDB.from_pyalpm(pkg) for pkg in DATABASES[database].search(query)]
        )

    aur_query = requests.get(
        f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={query}"
    ).json()

    packages.extend(AUR.from_query(result) for result in aur_query["results"])
    packages = sorted(packages)
    packages = {num + 1: pkg for num, pkg in enumerate(packages)}

    return packages


def get_pkg(pkg_name, verbose: Optional[bool] = False):
    for database in DATABASES:
        pkg = DATABASES[database].get_pkg(pkg_name)
        if pkg:
            return SyncDB.from_pyalpm(pkg)

    pkg = requests.get(
        f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={pkg_name}"
    ).json()["results"]
    if pkg:
        pkg = AUR.from_query(pkg[0])
        return pkg

    if verbose:
        console.print(f"[red]->[/red] No AUR package found for {pkg_name}")


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

    return {num: packages[num] for num in selections}
