import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

from . import utils
from .console import console


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

    def __init__(self, options: list[str], targets: list[str]) -> None:
        super().__init__(options, targets, self.run)

    def run(self) -> None:
        if not self.targets:
            utils.refresh()
            utils.upgrade()
        else:
            results = utils.search(" ".join(self.targets))
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

    def __init__(self, options: list[str], targets: list[str]) -> None:
        self.key = {
            "--refresh": self.refresh,
            "--sysupgrade": self.upgrade,
            "--clean": self.clean,
            "--search": self.search,
            "--info": self.info,
        }

        flags = {
            "refresh_flags": {"force": False},
            "install_flags": {
                "skip_verchecks": False,
                "skip_depchecks": False,
                "download_only": False,
            },
        }

        if options.count("--refresh") > 1:
            flags["refresh_flags"]["force"] = True
        if options.count("--nodeps") == 1:
            flags["install_flags"]["skip_verchecks"] = True
        elif options.count("--nodeps") > 1:
            flags["install_flags"]["skip_depchecks"] = True
        if options.count("--downloadonly") == 1:
            flags["install_flags"]["download_only"] = True

        self.flags = flags

        options = list(set(options))
        options = list(filter(lambda x: x in self.key.keys(), options))
        options = list(sorted(options, key=lambda x: list(self.key.keys()).index(x)))
        super().__init__(options, targets, self.run)

    def run(self) -> None:
        if not self.options:
            # TODO: Add error handling for missing args here
            self.install()
        elif any(opt in ["--clean", "--search", "--info"] for opt in self.options):
            for opt in self.options:
                self.key[opt]()
        else:
            for opt in set(self.options):
                self.key[opt]()
            if self.targets:
                self.install()

    def search(self) -> None:
        packages = utils.search(" ".join(self.targets))
        utils.print_pkglist(packages)

    def install(self) -> None:
        targets = utils.get_packages(*self.targets)
        if targets:
            utils.install(*targets, **self.flags["install_flags"])

    def refresh(self):
        utils.refresh(**self.flags["refresh_flags"])

    def upgrade(self) -> None:
        utils.upgrade()

    def download(self) -> None:
        targets = {"aur": [], "sync": []}
        packages = utils.get_packages(*self.targets)
        utils.download(*packages)

    def clean(self) -> None:
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

    def info(self) -> None:
        packages = utils.get_packages(*self.targets)
        utils.print_pkginfo(*packages)


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
        packages = utils.get_packages(*self.targets)
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
