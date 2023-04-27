import shlex
import subprocess
from dataclasses import dataclass
from typing import Callable

from . import utils
from .config import CACHEDIR
from .console import console
from .package import AURPackage


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
    args: list[str]
    run: Callable


class Nay(Operation):
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

    def __init__(self, options: list[str], args: list[str]) -> None:
        super().__init__(options, args, self.run)

    def run(self) -> None:
        if not self.args:
            utils.refresh()
            utils.upgrade()
        else:
            results = utils.search(" ".join(self.args))
            if not results:
                quit()
            utils.print_pkglist(results, include_num=True)
            packages = utils.select_packages(results)
            utils.refresh()
            utils.install(*packages)


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

    def __init__(self, options: list[str], args: list[str]) -> None:
        self.key = {
            "--refresh": self.refresh,
            "--refresh --refresh": self.force_refresh,
            "--sysupgrade": self.upgrade,
            "--downloadonly": self.download,
            "--clean": self.clean,
            "--search": self.search,
            "--info": self.info,
        }

        if options.count("--refresh") > 1:
            options.append("--refresh --refresh")
            options = list(filter(lambda opt: opt != "--refresh", options))
        elif options.count("--nodeps") > 1:
            options.append("--nodeps --nodeps")
            options = list(filter(lambda opt: opt != "--nodeps", options))

        options = list(set(options))
        options = list(sorted(options, key=lambda x: list(self.key.keys()).index(x)))
        super().__init__(options, args, self.run)

    def run(self) -> None:
        if not self.options:
            # TODO: Add error handling for missing args here
            self.install()
        elif any(opt in ["--clean", "--search", "--info"] for opt in self.options):
            for opt in self.options:
                self.key[opt]()
        elif "--downloadonly" in self.options:
            self.download()
        else:
            for opt in set(self.options):
                self.key[opt]()
            if self.args:
                self.install()

    def search(self) -> None:
        packages = utils.search(" ".join(self.args))
        utils.print_pkglist(packages)

    def install(self) -> None:
        targets = utils.get_packages(*self.args)
        if targets:
            if self.options.count("--nodeps") == 0:
                utils.install(*targets)
            elif self.options.count("--nopdeps") == 1:
                utils.install(*targets, nodeps=True)
            else:
                utils.install(*targets, nodeps_recursive=True)

    def force_refresh(self):
        utils.force_refresh()

    def refresh(self):
        utils.refresh()

    def upgrade(self) -> None:
        utils.upgrade()

    def download(self) -> None:
        targets = {"aur": [], "sync": []}
        packages = utils.get_packages(*self.args)
        for pkg in packages:
            if isinstance(pkg, AURPackage):
                targets["aur"].append(pkg)
            else:
                targets["sync"].append(pkg)

        for target in targets["aur"]:
            utils.get_pkgbuild(target, pkgdir=CACHEDIR)

        if targets["sync"]:
            subprocess.run(
                shlex.split(
                    f"sudo pacman -Sw {' '.join([pkg.name for pkg in targets['sync']])}"
                )
            )

    def clean(self) -> None:
        utils.clean()

    def info(self) -> None:
        packages = utils.get_packages(*self.args)
        utils.print_pkginfo(*packages)


class Query(Operation):
    """
    Query the local/sync databases. Purely a pacman wrapper

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

    def __init__(self, options: list[str], args: list[str]) -> None:
        super().__init__(options, args, self.run)

    def run(self) -> None:
        subprocess.run(
            shlex.split(f"pacman -Q {' '.join(self.options)} {' '.join(self.args)}")
        )


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

    def __init__(self, options: list[str], args: list[str]) -> None:
        super().__init__(options, args, self.run)

    def run(self) -> None:
        succeeded = []
        failed = []
        packages = utils.get_packages(*self.args)
        for pkg in packages:
            if pkg.name in self.args:
                succeeded.append(pkg)
            else:
                failed.append(pkg)

        if succeeded:
            for idx, pkg in enumerate(succeeded):
                idx += 1
                utils.get_pkgbuild(pkg)
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
                f"[bright_yellow] ->[/bright_yellow] Unable to find the following packages: {', '.join([arg for arg in failed])}"
            )


class Remove(Operation):
    """
    Remove packages from the system. Purely a pacman wrapper

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

    def __init__(self, options: list[str], args: list[str]) -> None:
        super().__init__(options, args, self.run)

    def run(self) -> None:
        subprocess.run(
            shlex.split(
                f"sudo pacman -R {' '.join(self.options)} {' '.join(self.args)}"
            )
        )


class Upgrade(Operation):
    """
    Upgrade specified targets. Purely a pacman wrapper.

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

    def __init__(self, options: list[str], args: list[str]) -> None:
        super().__init__(options, args, self.run)

    def run(self) -> None:
        subprocess.run(
            shlex.split(
                f"sudo pacman -U {' '.join(self.options)} {' '.join(self.args)}"
            )
        )
