import os
from dataclasses import dataclass
from typing import Callable, Optional
import subprocess
import shlex
from .package import SyncPackage, AURPackage, Package
import concurrent.futures
import networkx as nx

from .console import console
from .exceptions import ConflictingOptions


@dataclass
class Operation:
    """
    Boilerplate class for nay operations

    :param options: The options for the operation (e.g. ['u', 'y'])
    :type options: list[str]
    :param args: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :type args: list[str]
    :param run: The Callable for the operation. This is expected to be called after successful instantiation of the child class
    :type run: Callable

    :ivar options: The options for the operation (e.g. ['u', 'y'])
    :ivar args: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :ivar run: The Callable for the operation. This is expected to be called after successful instantiation of the child class
    """

    options: list[str]
    targets: list[str]
    run: Callable


class Sync(Operation):
    """Sync operations

    :param options: The options for the operation (e.g. ['u', 'y'])
    :type options: list[str]
    :param args: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :type args: list[str]
    :param run: The Callable for the operation. This is expected to be called after the class has been instantiated
    :type run: Callable

    :ivar options: The options for the operation (e.g. ['u', 'y'])
    :ivar args: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :ivar run: The Callable for the operation. This is expected to be called after the class has been instantiated
    """

    def __init__(self, options: list[str], targets: list[str]) -> None:

        self.key = {
            "--clean": self.clean,
            "--search": self.search,
            "--info": self.print_pkg_info,
        }

        flags = {
            "install_flags": {
                "skip_verchecks": False,
                "skip_depchecks": False,
                "download_only": False,
            },
        }

        self.parse_options(options)
        self.pacman_flags = []

        super().__init__(options, targets, self.run)

    def parse_options(self, options):
        conflicts = {
            "--clean": ["--refresh", "search", "--sysupgrade"],
            "--search": ["--sysupgrade", "--info", "--clean"],
        }
        for option in options:
            if option in conflicts.keys():
                for other in options:
                    if other in conflicts[option]:
                        try:
                            raise ConflictingOptions(
                                f"error: invalid option: '{option}' and '{other}' may not be used together"
                            )
                        except ConflictingOptions as err:
                            console.print(err)
                            quit()

    def run(self):
        if "--refresh" in self.options:
            subprocess.run(
                shlex.split(
                    f"sudo pacman -S {' '.join([option for option in self.options if option == '--refresh'])}"
                )
            )
            self.options = list(filter(lambda x: x != "--refresh", self.options))

        if "--clean" in self.options:
            self.clean()
            return

        if "--search" in self.options:
            self.search()
            return

        if "--info" in self.options:
            self.print_pkg_info()
            return

        self.install()

    def clean(self) -> None:
        from . import utils

        utils.clean_pacman()

        response = console.input(
            "\n[bright_blue]::[/bright_blue] Do you want to remove all other AUR packages from cache? [Y/n] "
        )

        if response.lower() == "y":
            console.print("removing AUR packages from cache...")
            utils.clean_cachedir()

        response = console.input(
            "\n[bright_blue]::[/bright_blue] Do you want to remove ALL untracked AUR files? [Y/n] "
        )

        if response.lower() == "y":
            console.print("removing untracked AUR files from cache...")
            utils.clean_untracked()

    def search(self) -> None:
        from . import db

        packages = db.search(" ".join(self.targets))
        db.print_pkglist(packages)

    def print_pkg_info(self) -> None:
        from . import db

        packages = db.get_packages(*self.targets)
        db.print_pkginfo(*packages)

    def install(self, targets: Optional[list[Package]] = None) -> None:
        from . import db
        from . import utils
        from .package import SyncPackage, AURPackage
        from rich.table import Table, Column

        def preview_job(
            sync_explicit: Optional[list[SyncPackage]] = None,
            sync_depends: Optional[list[SyncPackage]] = None,
            aur_explicit: Optional[list[AURPackage]] = None,
            aur_depends: Optional[list[AURPackage]] = None,
        ) -> None:

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

        def get_missing_pkgbuild(*packages: AURPackage, verbose=False):
            missing = []
            for pkg in packages:
                if not pkg.pkgbuild_exists:
                    missing.append(pkg)
                else:
                    if verbose:
                        console.print(
                            f"[notify]::[/notify] PKGBUILD up to date, skipping download: [notify]{pkg.name}"
                        )

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                for num, pkg in enumerate(missing):
                    executor.submit(utils.get_pkgbuild, pkg, force=True)
                    if verbose:
                        console.print(
                            f"[notify]::[/notify] ({num+1}/{len(missing)}) Downloaded PKGBUILD: [notify]{pkg.name}"
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

        skip_verchecks = False
        skip_depchecks = False
        download_only = False
        pacman_flags = []

        if self.options.count("--nodeps") >= 1:
            if self.options.count("--nodeps") == 1:
                skip_verchecks = True
                pacman_flags.append("--nodeps")
            else:
                skip_depchecks = True
                pacman_flags.extend(["--nodeps", "--nodeps"])

        if "--downloadonly" in self.options:
            download_only = True
            pacman_flags.extend(["--downloadonly"])

        if targets is None:
            targets = db.get_packages(*self.targets)

        sync_explicit = [
            target for target in targets if isinstance(target, SyncPackage)
        ]
        aur_explicit = [target for target in targets if isinstance(target, AURPackage)]

        if skip_depchecks is True:
            preview_job(sync_explicit=sync_explicit, aur_explicit=aur_explicit)
            if aur_explicit:
                get_missing_pkgbuild(*aur_explicit, verbose=True)
                preview_aur(*aur_explicit)
                prompt_proceed()
                utils.install_aur(
                    *aur_explicit,
                    skip_depchecks=True,
                    download_only=download_only,
                )
            if sync_explicit:
                utils.install_sync(*sync_explicit, pacman_flags=pacman_flags)

        aur_tree = db.get_dependency_tree(*aur_explicit, recursive=False)
        aur_depends = db.get_aur_depends(aur_tree, skip_verchecks=skip_verchecks)
        sync_depends = db.get_sync_depends(*aur_explicit)

        preview_job(sync_explicit, sync_depends, aur_explicit, aur_depends)

        aur = aur_explicit + aur_depends
        get_missing_pkgbuild(*aur, verbose=True)
        preview_aur(*aur)
        prompt_proceed()
        if aur_depends:
            aur_tree = nx.compose(aur_tree, db.get_dependency_tree(*aur_depends))
        get_missing_pkgbuild(
            *[pkg for pkg in aur_tree if pkg not in aur], verbose=False
        )

        if aur_tree:
            install_order = [layer for layer in nx.bfs_layers(aur_tree, *aur_explicit)][
                ::-1
            ]
            for layer in install_order:
                utils.install_aur(*layer, download_only=download_only)

        if sync_explicit:
            utils.install_sync(*sync_explicit, pacman_flags=pacman_flags)


class Nay(Sync):
    """
    Pyaura-specific operations

    :param options: The options for the operation (e.g. ['u', 'y'])
    :type options: list[str]
    :param args: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :type args: list[str]
    :param run: The Callable for the operation. This is expected to be called after the class has been instantiated
    :type run: Callable

    :ivar options: The options for the operation (e.g. ['u', 'y'])
    :ivar args: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :ivar run: The Callable for the operation. This is expected to be called after the class has been instantiated
    """

    def __init__(self, options: list[str], targets: list[str]) -> None:
        super().__init__(options, targets)

    def run(self) -> None:
        if not self.targets:
            subprocess.run(shlex.split("sudo pacman -Syu"))
        else:
            from . import db

            results = db.search(" ".join(self.targets))
            if not results:
                return
            db.print_pkglist(results, include_num=True)
            targets = db.select_packages(results)
            subprocess.run(shlex.split("sudo pacman -Sy"))
            self.install(targets)


class GetPKGBUILD(Operation):
    """
    Get PKGBUILD from specified args

    :param options: The options for the operation (e.g. ['u', 'y'])
    :type options: list[str]
    :param args: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :type args: list[str]
    :param run: The Callable for the operation. This is expected to be called after the class has been instantiated
    :type run: Callable

    :ivar options: The options for the operation (e.g. ['u', 'y'])
    :ivar args: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :ivar run: The Callable for the operation. This is expected to be called after the class has been instantiated
    """

    def __init__(self, options: list[str], targets: list[str]) -> None:
        super().__init__(options, targets, self.run)

    def run(self) -> None:
        succeeded = []
        failed = []
        from . import db
        from . import utils

        packages = db.get_packages(*self.targets)
        for pkg in packages:
            if pkg.name in self.targets:
                succeeded.append(pkg)
            else:
                failed.append(pkg)

        if succeeded:
            for idx, pkg in enumerate(succeeded):
                idx += 1
                utils.get_pkgbuild(pkg, os.getcwd())
                if pkg.db == "aur":
                    console.print(
                        f"[bright_blue]::[/bright_blue] ({idx}/{len(succeeded)}) Downloaded PKGBIULD: {pkg.name}"
                    )
                else:
                    console.print(
                        f"[bright_blue]::[/bright_blue] ({idx}/{len(succeeded)}) Downloaded PKGBIULD from ABS: {pkg.name}"
                    )

        if failed:
            console.print(
                f"[bright_red] ->[/bright_yellow] Unable to find the following packages: {', '.join([arg for arg in failed])}"
            )


class Wrapper(Operation):
    def __init__(
        self,
        operation: str,
        options: list[str],
        targets: list[str],
        sudo: Optional[bool] = False,
    ) -> None:
        self.operation = operation
        self.options = options
        self.targets = targets
        self.sudo = sudo
        super().__init__(options, targets, self.run)

    def run(self):
        command = f"pacman {self.operation} {' '.join(opt for opt in self.options)} {' '.join(target for target in self.targets)}"
        if self.sudo is True:
            command = f"sudo {command}"

        subprocess.run(shlex.split(command))


class Upgrade(Wrapper):
    def __init__(self, options: list[str], targets: list[str]):
        super().__init__("-U", options, targets, True)


class Remove(Wrapper):
    def __init__(self, options: list[str], targets: list[str]):
        super().__init__("-R", options, targets, True)


class Query(Wrapper):
    def __init__(self, options: list[str], targets: list[str]):
        super().__init__("-Q", options, targets)
