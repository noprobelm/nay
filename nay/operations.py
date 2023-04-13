from .config import CACHEDIR
from . import utils
from dataclasses import dataclass
import subprocess
import shlex
from typing import Optional, Callable


@dataclass
class Nay:
    """Pyaura-specific operations"""

    args: "Args"

    def run(self):
        if not self.args:
            utils.upgrade()
        else:
            utils.refresh(verbose=False)
            packages = utils.search(" ".join(self.args["args"]))
            utils.print_pkglist(packages, include_num=True)
            packages = utils.select_packages(packages)
            utils.install([packages[selection] for selection in packages])


@dataclass
class Sync:
    """Sync operations"""

    args: "Args"

    def __post_init__(self):
        self.key = {
            "y": self.refresh,
            "u": self.upgrade,
            "w": self.download,
            "c": self.clean,
            "s": self.query,
            "i": self.info,
        }

    def run(self):
        if not self.args["options"]:
            # Add error handling for missing args here
            self.install()
        elif any(opt in ["c", "s", "i"] for opt in self.args["options"]):
            for opt in set(self.args["options"]):
                self.key[opt]()
        else:
            for opt in set(self.args["options"]):
                self.key[opt]()
            if self.args["args"]:
                self.install()

    def query(self):
        packages = utils.search(" ".join(self.args["args"]))
        utils.print_pkglist(packages)

    def install(self):
        targets = []
        for arg in self.args["args"]:
            pkg = utils.get_pkg(arg, verbose=True)
            if pkg:
                targets.append(pkg)
        if targets:
            utils.install(targets)

    def refresh(self, force: Optional[bool] = False):
        utils.refresh(force=force)

    def upgrade(self):
        utils.upgrade()

    def download(self):
        packages = {"aur": [], "sync": []}

        for target in self.args["args"]:
            pkg = utils.get_pkg(target, verbose=True)
            if pkg:
                if pkg.db == "aur":
                    packages["aur"].append(pkg)
                else:
                    packages["sync"].append(pkg)

        for pkg in packages["aur"]:
            utils.get_pkgbuild(pkg, clonedir=CACHEDIR)

        if packages["sync"]:
            subprocess.run(
                shlex.split(
                    f"sudo pacman -Sw {' '.join([pkg.name for pkg in packages['sync']])}"
                )
            )

    def clean(self):
        utils.clean()

    def info(self, targets):
        packages = [utils.get_pkg(target) for target in targets]
        utils.print_pkginfo(packages)


@dataclass
class Query:
    """Query the local/sync databases. Purely pacman"""

    args: "Args"

    def run(self):
        subprocess.run(
            shlex.split(
                f"sudo pacman -Q{''.join(self.args['options'])} {' '.join(self.args['args'])}"
            )
        )


@dataclass
class GetPKGBUILD:
    """Get PKGBUILD from specified args"""

    args: "Args"

    def run(self):
        for pkg in self.args:
            utils.get_pkgbuild(pkg)


@dataclass
class Remove:
    """Remove packages from the system"""

    args: "Args"

    def run(self):
        print(self.args["options"])
        print(self.args["args"])
        print(" ".join(self.args["args"]))
        subprocess.run(
            shlex.split(
                f"sudo pacman -R{''.join(self.args['options'])} {' '.join(self.args['args'])}"
            )
        )
