import os
import shlex
import subprocess
from typing import Callable, Optional
from dataclasses import dataclass
from .db import SyncDatabase, LocalDatabase
from .aur import AUR


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
        self.sync_db = SyncDatabase(self.root, self.dbpath, self.config)
        self.local_db = LocalDatabase(self.root, self.dbpath)
        self.aur = AUR()

    def wrap_pacman(self, params: list[str], sudo: bool = False):
        prefix = "sudo " if sudo is True else ""
        params.extend([f"--dbpath {self.dbpath}", f"--root {self.root}"])
        subprocess.run(shlex.split(f"{prefix}pacman {' '.join([p for p in params])}"))
