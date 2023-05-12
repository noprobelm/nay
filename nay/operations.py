import shlex
import subprocess
from dataclasses import dataclass


@dataclass
class Operation:
    dbpath: str
    root: str
    config: str
    cachedir: str
    gpgdir: str
    hookdir: str
    logfile: str
    targets: list
    verbose: bool
    arch: bool
    color: str
    debug: bool
    noconfirm: bool
    disable_download_timeout: bool
    sysroot: bool
    pacman_params: list[str]

    def __post_init__(self):
        import configparser
        from .aur import AUR
        import pyalpm
        from .console import NayConsole

        self.console = NayConsole()
        self.wrapper_prefix = type(self).__name__.lower()
        handle = pyalpm.Handle(self.root, self.dbpath)
        parser = configparser.ConfigParser(allow_no_value=True)
        parser.read(self.config)

        self.local = handle.get_localdb()

        self.sync = {}
        for section in parser.sections():
            if section != "options":
                self.sync[section] = handle.register_syncdb(
                    section, pyalpm.SIG_DATABASE_OPTIONAL
                )

        self.aur = AUR(self.sync, self.local)

    @property
    def db_params(self):
        db_params = [
            f"--{self.wrapper_prefix}",
            f"--dbpath {self.dbpath}",
            f"--root {self.root}",
        ]
        return db_params

    def wrap_pacman(self, sudo: bool):
        prefix = "sudo " if sudo is True else ""
        params = self.pacman_params + [" ".join(self.targets)]
        subprocess.run(shlex.split(f"{prefix}pacman {' '.join([p for p in params])}"))


from dataclasses import dataclass
from .operations import Operation


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
