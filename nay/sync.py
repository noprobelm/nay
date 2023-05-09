from nay.operations import Operation
from nay.exceptions import ConflictingOptions
import subprocess
import shlex
import pathlib
from nay.db import Manager, SyncDatabase, AUR
from nay.utils import clean_cachedir, clean_untracked


class Sync(Operation):
    """Sync operations

    :param options: The options for the operation (e.g. ['-u', '-y'])
    :type options: list[str]
    :param targets: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :type targets: list[str]
    :param run: The Callable for the operation. This is expected to be called after successful instantiation of the child class
    :type run: Callable

    :ivar options: The options for the operation (e.g. ['-u', '-y'])
    :ivar args: The args for the operation (e.g. ['pkg1', 'pkg2'])
    :ivar run: The Callable for the operation. This is expected to be called after successful instantiation of the child class
    """

    def __init__(
        self,
        root: pathlib.Path,
        dbpath: pathlib.Path,
        config: pathlib.Path,
        targets: list,
        clean: int = 0,
        info: bool = False,
        _list: bool = False,
        search: bool = False,
        refresh: int = 0,
        sysupgrade: bool = False,
        nodeps: int = 0,
        downloadonly: bool = False,
        **kwargs,
    ) -> None:
        self.clean = clean
        self.info = info
        self._list = _list
        self.search = search
        self.refresh = refresh
        self.sysupgrade = sysupgrade
        self.nodeps = nodeps
        self.downloadonly = downloadonly
        self.manager = Manager(root, dbpath, config)
        super().__init__(root, dbpath, config, targets, self.run)

    def parse_kwargs(self, kwargs):
        conflicts = {
            "clean": ["refresh", "search", "sysupgrade"],
            "search": ["sysupgrade", "info", "clean"],
            "info": ["search"],
            "sysupgrade": ["search, clean", "info"],
            "nodeps": [],
            "downloadonly": [],
            "refresh": ["clean"],
        }

        for kwarg in kwargs:
            for other in kwargs:
                if other in conflicts[kwarg]:
                    raise ConflictingOptions(
                        f"error: invalid option: '{kwarg}' and '{other}' may not be used together"
                    )
        return kwargs

    def run(self) -> None:
        if self.refresh:
            self.refresh_database()

        if self.sysupgrade is True:
            self.upgrade_system()
            if not self.targets:
                return

        if self.clean:
            self.clean_cache()
            return

        if self.search is True:
            self.search_database()
            return

        if self.info is True:
            if not self.targets:
                params = [
                    "--sync",
                    "--info",
                ]
                self.wrap_pacman(params, sudo=False)
            else:
                packages = self.manager.get_packages(*self.targets)
                self.manager.print_pkginfo(*packages)

            return

        if not self.targets:
            raise MissingTargets("error: no targets specified (use -h for help)")

        self.install()

    def refresh_database(self) -> None:
        params = ["--sync"]
        for _ in range(self.refresh):
            params.append("--refresh")
        self.wrap_pacman(params, sudo=True)

    def upgrade_system(self) -> None:
        params = ["--sync", "--sysupgrade"]
        self.wrap_pacman(params, sudo=True)

    def clean_cache(self) -> None:
        params = ["--sync"]
        for _ in range(self.clean):
            params.append("--clean")

        self.wrap_pacman(params, sudo=True)
        clean_cachedir()
        clean_untracked()

    def search_database(self) -> None:
        if not self.targets:
            params = [
                "--sync",
                "--search",
            ]
            self.wrap_pacman(params, sudo=False)
        else:
            packages = self.manager.search(" ".join(self.targets))
            self.manager.print_pkglist(packages, include_num=False)

    def install(self) -> None:
        from . import install

        skip_verchecks = False
        skip_depchecks = False
        download_only = False
        pacman_flags = []

        if self.nodeps:
            if self.nodeps == 1:
                skip_verchecks = True
                pacman_flags.append("--nodeps")
            else:
                skip_depchecks = True
                pacman_flags.extend(["--nodeps", "--nodeps"])

        if self.downloadonly is True:
            download_only = True
            pacman_flags.append("--downloadonly")

        install_kwargs = {
            "skip_verchecks": skip_verchecks,
            "skip_depchecks": skip_depchecks,
            "download_only": download_only,
            "pacman_flags": pacman_flags,
        }

        install.install(
            skip_verchecks=skip_verchecks,
            skip_depchecks=skip_depchecks,
            download_only=download_only,
            pacman_flags=pacman_flags,
            *self.targets,
        )
