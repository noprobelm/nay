from .operations import Operation
from dataclasses import dataclass


@dataclass
class Transaction(Operation):
    nodeps: bool
    assume_installed: list[str]
    dbonly: bool
    noprogressbar: bool
    noscriptlet: bool
    print_only: bool
    print_format: str

    def run(self) -> None:
        sudo = True
        if "--print" in self.pacman_params:
            sudo = False

        self.wrap_pacman(sudo=sudo)


@dataclass
class Remove(Transaction):
    cascade: bool
    nosave: bool
    recursive: bool
    unneeded: bool


@dataclass
class Upgrade(Transaction):
    download_only: bool
    asdeps: bool
    asexplicit: bool
    ignore: bool
    needed: bool
    overwrite: bool


@dataclass
class Query(Operation):
    changelog: bool
    deps: bool
    explicit: bool
    group: bool
    info: bool
    check: bool
    _list: bool
    foreign: bool
    native: bool
    owns: bool
    _file: bool
    quiet: bool
    search: bool
    unrequired: bool

    def run(self) -> None:
        self.wrap_pacman(sudo=False)


@dataclass
class Database(Operation):
    asdeps: bool
    asexplicit: bool
    check: bool
    quiet: bool

    def run(self) -> None:
        sudo = False
        if self.targets:
            self.sudo = True
        if "--check" in self.pacman_params:
            sudo = False

        self.wrap_pacman(sudo=sudo)


@dataclass
class Files(Operation):
    refresh: bool
    _list: bool
    regex: str
    quiet: bool
    machinereadable: bool

    def run(self) -> None:
        sudo = False
        if "--refresh" in self.pacman_params:
            sudo = True
        self.wrap_pacman(sudo=sudo)


@dataclass
class Deptest(Operation):
    def run(self):
        self.wrap_pacman(sudo=False)
