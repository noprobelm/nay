import os
import shutil
import subprocess
import shlex
import requests
import re
from typing import Optional

from .package import Sync, AUR
from .db import DATABASES, INSTALLED
from .console import console
from rich.console import Group
from rich.text import Text
from .config import CACHEDIR


SRCDIR = os.getcwd()
SORT_PRIORITIES = {"db": {"core": 0, "extra": 1, "community": 2, "multilib": 4}}
for num, db in enumerate(DATABASES):
    num += max([num for num in SORT_PRIORITIES["db"].values()])
    if db not in SORT_PRIORITIES["db"].keys():
        SORT_PRIORITIES["db"][db] = num
SORT_PRIORITIES["db"]["aur"] = max([num for num in SORT_PRIORITIES["db"].values()])

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
            shutil.rmtree(obj)
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
    )


def makepkg(pkg, clonedir, install=True, clean: Optional[bool] = False):
    """Run makepkg on a PKGBUILD"""
    os.chdir(f"{clonedir}/{pkg.name}")
    if install:
        subprocess.run(shlex.split("makepkg -si"))
    else:
        subprocess.run(shlex.split("makepkg -s"))

    if clean:
        os.chdir("../")
        shutil.rmtree(f"{os.getcwd()}/{pkg.name}", ignore_errors=True)

    os.chdir(SRCDIR)


def get_aur_dependencies(*packages):

    depends = []
    aur_query = requests.get(
        f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join([pkg for pkg in packages])}"
    ).json()

    packages = [AUR.from_info_query(query) for query in aur_query["results"]]
    for pkg in packages:
        info_query = pkg.info_query
        if "MakeDepends" in info_query.keys():
            depends.extend(info_query["MakeDepends"])
        if "CheckDepends" in info_query.keys():
            depends.extend(info_query["CheckDepends"])
        if "Depends" in info_query.keys():
            depends.extend(info_query["Depends"])


def install(*packages, top=False):
    """Install a package based on package.Package data"""
    sync = [pkg for pkg in packages if isinstance(pkg, Sync)]
    aur = [pkg for pkg in packages if isinstance(pkg, AUR)]
    unresolved = []

    if sync:
        output = [f"{pkg.name}-{pkg.version}" for pkg in sync]
        console.print(
            f"Sync Explicit {len(sync)}: {', '.join([pkg for pkg in output])}"
        )
    if aur:
        output = [f"{pkg.name}-{pkg.version}" for pkg in aur]
        console.print(f"AUR Explicit {len(aur)}: {', '.join([pkg for pkg in output])}")

        if top:
            missing_pkgbuild = []
            depends = []
            for pkg in aur:
                info_query = pkg.info_query
                if "MakeDepends" in info_query.keys():
                    depends.extend(info_query["MakeDepends"])
                if "CheckDepends" in info_query.keys():
                    depends.extend(info_query["CheckDepends"])
                if "Depends" in info_query.keys():
                    depends.extend(info_query["Depends"])

                depends = [dep for dep in depends if dep not in INSTALLED]

                # Note we're not checking if installed dependencies are updated to the latest version here... Which is
                # why pacman should inherently run as -Syu prior to / along with any package install in the first place.
                aur_query = requests.get(
                    f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join([depends for depends in depends])}"
                ).json()

                depends = [
                    AUR.from_info_query(result)
                    for result in aur_query["results"]
                    if result["Name"] not in INSTALLED
                ]

                output = [f"{dep.name}-{dep.version}" for dep in depends]
                console.print(
                    f"AUR Dependency ({len(depends)}): {', '.join([out for out in output])}"
                )

            for dep in depends:
                if not dep.pkgbuild_exists:
                    missing_pkgbuild.append(dep)
                else:
                    console.print(
                        f":: PKGBUILD up to date, skipping download: {dep.name}"
                    )
            missing_pkgbuild.extend([dep for dep in depends if not dep.pkgbuild_exists])

            for pkg in aur:
                if not pkg.pkgbuild_exists:
                    missing_pkgbuild.append(pkg)

                else:
                    console.print(
                        f":: PKGBUILD up to date, skipping download: {pkg.name}"
                    )

            for num, missing in enumerate(missing_pkgbuild):
                get_pkgbuild(missing)
                console.print(
                    f":: {num+1}/{len(missing)} Downloaded PKGBUILD: {missing.name}"
                )

            to_install = depends
            to_install.extend(aur)
            install(*to_install)

        else:
            for pkg in aur:
                if not pkg.pkgbuild_exists:
                    get_pkgbuild(pkg, CACHEDIR)

                with open(pkg.SRCINFO, "r") as f:
                    SRCINFO = [line for line in f.readlines()]

                depends = []
                opt_depends = []
                for line in SRCINFO:
                    line = line.strip()
                    if "depends" in line:
                        if "opt" in line:
                            opt_depend = (
                                re.search(r"(?<==)\s*(\w+-?\w+)", line).group(0).strip()
                            )
                            opt_depends.append(opt_depend)
                        else:
                            depend = (
                                re.search(r"(?<==)\s*(\w+-?\w+)", line).group(0).strip()
                            )
                            depends.append(depend)

                aur_query = requests.get(
                    f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join([depend for depend in depends])}"
                ).json()
                for result in aur_query["results"]:
                    if result["Name"] not in INSTALLED:
                        unresolved.append(AUR.from_info_query(result))

                # Recursion occurs here
                if unresolved:
                    if top:
                        install(*unresolved, top=True)

                makepkg(pkg, CACHEDIR)


def search(query: str, sortby: Optional[str] = "db"):
    """Query the sync databases and AUR"""
    packages = []

    for database in DATABASES:
        packages.extend(
            [Sync.from_pyalpm(pkg) for pkg in DATABASES[database].search(query)]
        )

    aur_query = requests.get(
        f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={query}"
    ).json()

    packages.extend(AUR.from_search_query(result) for result in aur_query["results"])
    packages = list(
        reversed(
            sorted(
                packages, key=lambda val: SORT_PRIORITIES[sortby][getattr(val, sortby)]
            )
        )
    )
    packages = {len(packages) - num: pkg for num, pkg in enumerate(packages)}

    return packages


def get_pkg(pkg_name):
    for database in DATABASES:
        pkg = DATABASES[database].get_pkg(pkg_name)
        if pkg:
            return Sync.from_pyalpm(pkg)

    pkg = requests.get(
        f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={pkg_name}"
    ).json()["results"]
    if pkg:
        pkg = AUR.from_info_query(pkg[0])
        return pkg

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

    selected = []
    for num in selections:
        try:
            selected.append(packages[num])
        except KeyError:
            pass

    return selected
