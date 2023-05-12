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
