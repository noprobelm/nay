import configparser
from dataclasses import dataclass

import pyalpm

from .console import NayConsole
from .exceptions import ConfigReadError, HandleCreateError
from .wrapper import Wrapper


@dataclass
class Operation(Wrapper):
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
    console: NayConsole

    def __post_init__(self):
        from .aur import AUR

        self.wrapper_prefix = type(self).__name__.lower()

        parser = self.__get_config_parser(self.config)
        handle = self.__get_handle(self.root, self.dbpath)

        self.local = self.__get_localdb(handle)
        self.sync = self.__get_syncdb(handle, parser)
        self.aur = AUR(self.local, self.console)

    @property
    def db_params(self):
        db_params = [
            f"--{self.wrapper_prefix}",
            f"--dbpath {self.dbpath}",
            f"--root {self.root}",
        ]
        return db_params

    def __get_handle(self, root, dbpath):
        try:
            return pyalpm.Handle(root, dbpath)
        except pyalpm.error as err:
            raise HandleCreateError(str(err))

    def __get_syncdb(
        self, handle: pyalpm.Handle, parser: configparser.ConfigParser
    ) -> dict[str, "pyalpm.Database"]:
        sync = {}
        for section in parser.sections():
            if section != "options":
                sync[section] = handle.register_syncdb(
                    section, pyalpm.SIG_DATABASE_OPTIONAL
                )

        return sync

    def __get_localdb(self, handle: pyalpm.Handle) -> "pyalpm.DataBase":
        return handle.get_localdb()

    def __get_config_parser(self, configdir: str) -> configparser.ConfigParser:
        parser = configparser.ConfigParser(allow_no_value=True)
        if not parser.read(configdir):
            raise ConfigReadError(
                f"error: config file {configdir} could not be read: no such file or directory"
            )

        return parser
