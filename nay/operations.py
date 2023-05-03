import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional
import re

from .console import console
from .exceptions import ConflictingOptions, InvalidOption, MissingTargets, PacmanError


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

        self.options = self.parse_options(options)

        super().__init__(options, targets, self.run)

    def parse_options(self, options):
        mapper = {
            "-c": "--clean",
            "-s": "--search",
            "-i": "--info",
            "-u": "--sysupgrade",
            "-w": "--downloadonly",
            "-y": "--refresh",
        }

        for num, option in enumerate(options):
            if option in mapper.keys():
                options[num] = mapper[option]

        conflicts = {
            "--clean": ["--refresh", "search", "--sysupgrade"],
            "--search": ["--sysupgrade", "--info", "--clean"],
            "--info": ["--search"],
            "--sysupgrade": ["--search, --clean", "--info"],
            "--nodeps": [],
            "--downloadonly": [],
            "--refresh": ["--clean"],
        }

        for option in options:
            for other in options:
                try:
                    if other in conflicts[option]:
                        raise ConflictingOptions(
                            f"error: invalid option: '{option}' and '{other}' may not be used together"
                        )
                except KeyError:
                    raise InvalidOption(f"error: invalid option '{option}")
        return options

    def run(self):
        if "--refresh" in self.options:
            self.refresh()

        if "--sysupgrade" in self.options:
            self.sysupgrade()

        if "--clean" in self.options:
            self.clean()
            return

        if "--search" in self.options:
            self.search()
            return

        if "--info" in self.options:
            self.print_pkg_info()
            return

        if not self.targets:
            raise MissingTargets("error: no targets specified (use -h for help)")

        self.install()

    def refresh(self):
        subprocess.run(
            shlex.split(
                f"sudo pacman -S {' '.join([option for option in self.options if option == '--refresh'])}"
            )
        )

    def sysupgrade(self):
        subprocess.run(shlex.split(f"sudo pacman -Su"))

    def clean(self) -> None:
        subprocess.run(
            shlex.split(
                f"sudo pacman -S {' '.join([option for option in self.options if option == '--clean'])}"
            )
        )
        from . import clean

        clean.clean_cachedir()
        clean.clean_untracked()

    def search(self) -> None:
        if not self.targets:
            subprocess.run(shlex.split("pacman -S --search"))
            return

        from . import db

        packages = db.search(" ".join(self.targets))
        db.print_pkglist(packages)

    def print_pkg_info(self) -> None:
        if not self.targets:
            subprocess.run(shlex.split("pacman -S --info"))

        from . import db

        packages = db.get_packages(*self.targets)
        db.print_pkginfo(*packages)

    def install(self) -> None:
        from . import install

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
            pacman_flags.append("--downloadonly")

        install_kwargs = {
            "skip_verchecks": skip_verchecks,
            "skip_depchecks": skip_depchecks,
            "download_only": download_only,
            "pacman_flags": pacman_flags,
        }

        install.install(*self.targets, **install_kwargs)


class Nay(Sync):
    """
    Nay-specific operations

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
            self.targets = db.select_packages(results)
            subprocess.run(shlex.split("sudo pacman -Sy"))
            self.install()


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
        from . import db, get

        packages = db.get_packages(*self.targets)
        for pkg in packages:
            if pkg.name in self.targets:
                succeeded.append(pkg)
            else:
                failed.append(pkg)

        if succeeded:
            for idx, pkg in enumerate(succeeded):
                idx += 1
                get.get_pkgbuild(pkg, os.getcwd())
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

        try:
            subprocess.run(
                shlex.split(command),
                check=True,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as err:
            stderr = err.stderr.decode().strip()
            stderr = re.sub(f"pacman", "nay", stderr)
            raise PacmanError(stderr)
        else:
            pass


class Upgrade(Wrapper):
    def __init__(self, options: list[str], targets: list[str]):
        super().__init__("-U", options, targets, True)


class Remove(Wrapper):
    def __init__(self, options: list[str], targets: list[str]):
        super().__init__("-R", options, targets, True)


class Query(Wrapper):
    def __init__(self, options: list[str], targets: list[str]):
        super().__init__("-Q", options, targets)
