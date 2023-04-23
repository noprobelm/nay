import os
import shutil
import subprocess
import shlex
import requests
import re
from typing import Optional

from .package import Sync, AUR
from .db import DATABASES
from .console import console
from rich.console import Group
from rich.text import Text
from rich.table import Table, Column
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


def makepkg(pkg, clonedir, flags: str, clean: Optional[bool] = False):
    """Run makepkg on a PKGBUILD"""
    os.chdir(f"{clonedir}/{pkg.name}")
    subprocess.run(shlex.split(f"makepkg -{flags}"))

    if clean:
        os.chdir("../")
        shutil.rmtree(f"{os.getcwd()}/{pkg.name}", ignore_errors=True)


def get_aur_dependencies(*packages, recursive=True):

    depends = []
    for pkg in packages:
        info_query = pkg.info_query
        if "MakeDepends" in info_query.keys():
            depends.extend(info_query["MakeDepends"])
        if "CheckDepends" in info_query.keys():
            depends.extend(info_query["CheckDepends"])
        if "Depends" in info_query.keys():
            depends.extend(info_query["Depends"])

    aur_query = requests.get(
        f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join([depends for depends in depends])}"
    ).json()

    depends = [AUR.from_info_query(result) for result in aur_query["results"]]

    if depends and recursive == True:
        depends.extend(get_aur_dependencies(*depends))

    return depends


def install(*packages):
    """Install a package based on package.Package data"""
    sync_explicit = [pkg for pkg in packages if isinstance(pkg, Sync)]
    aur_explicit = [pkg for pkg in packages if isinstance(pkg, AUR)]
    aur_depends = []

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

        aur_depends = get_aur_dependencies(*aur_explicit, recursive=False)
        output = [f"{dep.name}-{dep.version}" for dep in aur_depends]
        console.print(
            f"AUR Dependency ({len(aur_depends)}): {', '.join([out for out in output])}"
        )

    aur = [pkg for total in [aur_explicit, aur_depends] for pkg in total]
    missing = []

    for pkg in aur:
        if not pkg.pkgbuild_exists:
            missing.append(pkg)
        else:
            console.print(f":: PKGBUILD up to date, skipping download: {pkg.name}")

    for num, missing in enumerate(missing):
        get_pkgbuild(missing)
        console.print(f":: {num+1}/{len(missing)} Downloaded PKGBUILD: {missing.name}")

    install_preview = Table.grid(
        Column("num", justify="right"),
        Column("pkgname", width=50, justify="left"),
        Column("pkgbuild_exists"),
        padding=(0, 1, 0, 1),
    )
    for num, pkg in enumerate(aur):
        # TODO: Fix hardcoded "Build Files Exist" -- I'm not how we'd encounter a scenario where we got here and they __dont__ exist
        install_preview.add_row(str(len(aur) - num), pkg.name, "Build Files Exist")

    console.print(install_preview)

    proceed_prompt = console.input(
        "[bright_green]==>[/bright_green] Install packages? [Y/n] "
    )
    if not proceed_prompt.lower().startswith("y"):
        quit()

    child_depends = get_aur_dependencies(*aur_depends)
    for dep in child_depends:
        if not dep.pkgbuild_exists:
            get_pkgbuild(dep)

    aur.extend(child_depends)

    if sync_explicit:
        subprocess.run(
            shlex.split(f"sudo pacman -S {[pkg.name for pkg in sync_explicit]}")
        )

    targets = []
    for pkg in aur:
        makepkg(pkg, CACHEDIR, "fsd")
        pattern = f"{pkg.name}-{pkg.version}-"
        for obj in os.listdir(os.path.join(CACHEDIR, pkg.name)):
            if pattern in obj and obj.endswith("zst"):
                targets.append(os.path.join(CACHEDIR, pkg.name, obj))

    subprocess.run(shlex.split(f"sudo pacman -U {' '.join(targets)}"))


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

        # Ignore invalid selections by the user
        except KeyError:
            pass

    aur_query = requests.get(
        f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join([pkg.name for pkg in selected])}"
    ).json()

    selected = [AUR.from_info_query(result) for result in aur_query["results"]]

    return selected
