import concurrent.futures
import os
import shlex
import subprocess
from typing import Optional, Union

import networkx as nx
from rich.table import Column, Table

from . import db, get
from .config import CACHEDIR
from .console import console
from .package import AURBasic, AURPackage, Package, SyncPackage


def makepkg(pkg: Package, pkgdir: str, flags: str) -> None:
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
    return_code = subprocess.run(shlex.split(f"makepkg -{flags}")).returncode
    if return_code != 0:
        console.print(f"[red] -> error making: {pkg.name}-exit status {return_code}")
        console.print(
            f"[red] Failed to install {pkg.name}. Manual intervention is required"
        )
        quit()


def install_aur(
    *packages: AURPackage,
    skip_depchecks: Optional[bool] = False,
    download_only: Optional[bool] = False,
):
    targets = []
    for pkg in packages:
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


def install_sync(*packages: SyncPackage, pacman_flags: list[str]):
    subprocess.run(
        shlex.split(
            f"sudo pacman -S{' '.join(flag for flag in pacman_flags)} {' '.join([pkg.name for pkg in packages])}"
        )
    )


def preview_packages(
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
                executor.submit(get.get_pkgbuild, pkg, force=True)
                if verbose:
                    console.print(
                        f"[notify]::[/notify] ({num+1}/{len(missing)}) Downloaded PKGBUILD: [notify]{pkg.name}"
                    )
    else:
        for num, pkg in enumerate(missing):
            get.get_pkgbuild(pkg, force=True)
            if verbose:
                console.print(
                    f"[notify]::[/notify] {num+1}/{len(missing)} Downloaded PKGBUILD: [notify]{pkg.name}"
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
    prompt = console.input("[bright_green]==>[/bright_green] Install packages? [Y/n] ")
    if not prompt.lower().startswith("y"):
        quit()


def install(
    *targets: Union[str, SyncPackage, AURPackage, AURBasic],
    pacman_flags: bool,
    skip_verchecks: Optional[bool] = False,
    skip_depchecks: Optional[bool] = False,
    download_only: Optional[bool] = False,
):

    query = [target for target in targets if isinstance(target, str)]
    packages = [target for target in targets if isinstance(target, Package)]
    if query:
        packages.extend(db.get_packages(*query))
    if not packages:
        quit()

    sync_explicit = [pkg for pkg in packages if isinstance(pkg, SyncPackage)]
    aur_explicit = [pkg for pkg in packages if isinstance(pkg, AURPackage)]

    if skip_depchecks is True:
        preview_packages(sync_explicit=sync_explicit, aur_explicit=aur_explicit)
        if aur_explicit:
            get_missing_pkgbuild(*aur_explicit, verbose=True)
            preview_aur(*aur_explicit)
            prompt_proceed()
            install_aur(
                *aur_explicit,
                skip_depchecks=True,
                download_only=download_only,
            )
        if sync_explicit:
            install_sync(*sync_explicit, pacman_flags=pacman_flags)

        return

    aur_tree = db.get_dependency_tree(*aur_explicit, recursive=False)
    aur_depends = db.get_aur_depends(aur_tree, skip_verchecks=skip_verchecks)
    sync_depends = db.get_sync_depends(*aur_explicit)

    preview_packages(sync_explicit, sync_depends, aur_explicit, aur_depends)

    aur = aur_explicit + aur_depends
    get_missing_pkgbuild(*aur, verbose=True)
    preview_aur(*aur)
    prompt_proceed()
    if aur_depends:
        aur_tree = nx.compose(aur_tree, db.get_dependency_tree(*aur_depends))
    get_missing_pkgbuild(*[pkg for pkg in aur_tree if pkg not in aur], verbose=False)

    if aur_tree:
        install_order = [layer for layer in nx.bfs_layers(aur_tree, *aur_explicit)][
            ::-1
        ]
        for layer in install_order:
            install_aur(*layer, download_only=download_only)

    if sync_explicit:
        install_sync(*sync_explicit, pacman_flags=pacman_flags)
