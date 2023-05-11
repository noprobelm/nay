import configparser
import shlex
import subprocess
from dataclasses import dataclass
from .aur import AUR
from pyalpm import Handle
import pyalpm
from .console import NayConsole


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

    def __post_init__(self):
        self.console = NayConsole()
        self.wrapper_prefix = type(self).__name__.lower()
        handle = Handle(self.root, self.dbpath)
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
    def wrapper_params(self):
        wrapper_params = [
            f"--{self.wrapper_prefix}",
            f"--dbpath {self.dbpath}",
            f"--root {self.root}",
        ]
        return wrapper_params

    def wrap_pacman(self, params: list[str], sudo: bool = False):
        prefix = "sudo " if sudo is True else ""
        params.extend([f"--dbpath {self.dbpath}", f"--root {self.root}"])
        subprocess.run(shlex.split(f"{prefix}pacman {' '.join([p for p in params])}"))
