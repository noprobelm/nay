from dataclasses import dataclass
from typing import Optional, Callable
import subprocess
import shlex
from .package import AUR
from .console import console
from .config import CACHEDIR
from . import utils


@dataclass
class Operation:
    """Boilerplate class for Nay operations"""

    options: list[str]
    args: list[str]
    run: Callable


class Nay(Operation):
    """Pyaura-specific operations"""

    def __init__(self, options: list[str], args: list[str]):
        super().__init__(options, args, self.run)

    def run(self):
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
    """Sync operations"""

    def __init__(self, options: list[str], args: list[str]):
        self.key = {
            "y": self.refresh,
            "u": self.upgrade,
            "w": self.download,
            "c": self.clean,
            "s": self.query,
            "i": self.info,
        }
        super().__init__(options, args, self.run)

    def run(self):
        if not self.options:
            # Add error handling for missing args here
            self.install()
        elif any(opt in ["c", "s", "i"] for opt in self.options):
            for opt in set(self.options):
                self.key[opt]()
        else:
            for opt in set(self.options):
                self.key[opt]()
            if self.args:
                self.install()

    def query(self):
        packages = utils.search(" ".join(self.args))
        utils.print_pkglist(packages)

    def install(self):
        targets = utils.get_packages(*self.args)
        if targets:
            utils.install(*targets)

    def refresh(self, force: Optional[bool] = False):
        utils.refresh(force=force)

    def upgrade(self):
        utils.upgrade()

    def download(self):
        targets = {"aur": [], "sync": []}
        packages = utils.get_packages(self.args)
        for pkg in packages:
            if isinstance(pkg, AUR):
                targets["aur"].append(pkg)
            else:
                targets["sync"].append(pkg)

        for target in targets["aur"]:
            utils.get_pkgbuild(target, clonedir=CACHEDIR)

        if targets["sync"]:
            subprocess.run(
                shlex.split(
                    f"sudo pacman -Sw {' '.join([pkg.name for pkg in packages['sync']])}"
                )
            )

    def clean(self):
        utils.clean()

    def info(self):
        packages = utils.get_packages(self.args)
        utils.print_pkginfo(packages)


class Query(Operation):
    """Query the local/sync databases. Purely pacman"""

    def __init__(self, options: list[str], args: list[str]):
        super().__init__(options, args, self.run)

    def run(self):
        subprocess.run(
            shlex.split(f"sudo pacman -Q{''.join(self.options)} {' '.join(self.args)}")
        )


class GetPKGBUILD(Operation):
    """Get PKGBUILD from specified args"""

    def __init__(self, options: list[str], args: list[str]):
        super().__init__(options, args, self.run)

    def run(self):
        succeeded = []
        failed = []
        packages = utils.get_packages(self.args)
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
    """Remove packages from the system"""

    def __init__(self, options: list[str], args: list[str]):
        super().__init__(options, args, self.run)

    def run(self):
        subprocess.run(
            shlex.split(f"sudo pacman -R{''.join(self.options)} {' '.join(self.args)}")
        )


class Upgrade(Operation):
    def __init__(self, options: list[str], args: list[str]):
        super().__init__(options, args, self.run)

    def run(self):
        subprocess.run(
            shlex.split(f"sudo pacman -U {''.join(self.options)} {' '.join(self.args)}")
        )
