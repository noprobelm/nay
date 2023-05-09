from nay.operations import Operation
import subprocess
import shlex
from nay.utils import clean_cachedir, clean_untracked
from nay.exceptions import MissingTargets
from typing import Optional
from dataclasses import dataclass
from .console import console, default
from rich.console import Group
from rich.text import Text
from .package import Package


@dataclass
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

    nodeps: int
    assume_installed: list[str]
    dbonly: bool
    noprogressbar: bool
    noscriptlet: bool
    print_only: bool
    print_format: str
    download_only: bool
    asdeps: bool
    asexplicit: bool
    ignore: bool
    needed: bool
    overwrite: bool
    clean: bool
    groups: bool
    info: bool
    _list: bool
    quiet: bool
    search: bool
    sysupgrade: bool
    refresh: int

    def run(self) -> None:
        if self.refresh:
            params = ["--sync"]
            for _ in range(self.refresh):
                params.append("--refresh")
            self.wrap_pacman(params, sudo=True)

        if self.sysupgrade is True:
            params = ["--sync", "--sysupgrade"]
            self.wrap_pacman(params, sudo=True)
            self.upgrade_system()
            if not self.targets:
                return

        if self.clean:
            self.clean_cache()
            return

        if self.search is True:
            if not self.targets:
                params = [
                    "--sync",
                    "--search",
                ]
                self.wrap_pacman(params, sudo=False)
                return

            packages = self.search_database()
            self.print_pkglist(packages, include_num=False)
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

            return

        if not self.targets:
            raise MissingTargets("error: no targets specified (use -h for help)")

        self.install()

    def upgrade_system(self) -> None:
        params = ["--sync", "--sysupgrade"]
        self.wrap_pacman(params, sudo=True)

    def clean_cache(self) -> None:
        params = ["--sync"]
        for _ in range(self.clean):
            params.append("--clean")

        self.wrap_pacman(params, sudo=True)

        if (
            console.input(
                "\n[bright_blue]::[/bright_blue] Do you want to remove all other AUR packages from cache? [Y/n] "
            ).lower()
            == "y"
        ):
            console.print("removing untracked AUR files from cache...")
            clean_cachedir()

        if (
            console.input(
                "\n[bright_blue]::[/bright_blue] Do you want to remove ALL untracked AUR files? [Y/n] "
            ).lower()
            == "y"
        ):
            console.print("removing AUR packages from cache...")

            clean_untracked()

    def search_database(self, sortby: Optional[str] = "db") -> dict[int, Package]:
        query = " ".join(self.targets)
        aur = self.aur.search(query)
        sync = self.sync_db.search(query)
        packages = aur + sync
        sort_priorities = {"db": {"core": 0, "extra": 1, "community": 2, "multilib": 4}}
        for num, db in enumerate(self.sync_db):
            num += max([num for num in sort_priorities["db"].values()])
            if db not in sort_priorities["db"].keys():
                sort_priorities["db"][db] = num
        sort_priorities["db"]["aur"] = max(
            [num for num in sort_priorities["db"].values()]
        )

        packages = list(
            reversed(
                sorted(
                    packages,
                    key=lambda val: sort_priorities[sortby][getattr(val, sortby)],
                )
            )
        )

        for num, pkg in enumerate(packages):
            if pkg.name == query:
                packages.append(packages.pop(num))

        packages = {len(packages) - num: pkg for num, pkg in enumerate(packages)}
        return packages

    def print_pkglist(
        self, packages: dict[int, Package], include_num: Optional[bool] = False
    ) -> None:
        """
        Print a sequence of passed packages
        :param packages: A dictionary of integers representing index to package results
        :type packages: dict[int, Package]
        :param include_num: Optional bool to indicate whether a package's index should be included in the print result or not. Default is False
        :type include_num: Optional[bool]
        """

        def get_size(pkg):
            return Text(f"{pkg.size}")

        def get_isize(pkg):
            return Text(f"{pkg.isize}")

        def get_votes(pkg):
            return Text(f"{pkg.votes}")

        def get_popularity(pkg):
            return Text("{:.2f}".format(pkg.popularity))

        def get_orphan(pkg):
            return Text("(Orphaned) ", style="bright_red") if pkg.orphaned else Text("")

        def get_flag_date(pkg):
            return (
                Text(f"(Out-of-date): {pkg.flag_date.strftime('%Y-%m-%d')}")
                if pkg.flag_date
                else Text("")
            )

        render_result = []

        for num in packages:
            pkg = packages[num]

            renderable = Text.assemble(
                Text(
                    pkg.db,
                    style=pkg.db if pkg.db in default.styles.keys() else "other_db",
                ),
                Text("/"),
                Text(f"{pkg.name} "),
                Text(f"{pkg.version} ", style="cyan"),
            )

            if isinstance(pkg, SyncPackage):
                renderable.append_text(Text(f"({get_size(pkg)} "))
                renderable.append_text(Text(f"{get_isize(pkg)}) "))
                local = self.localdb.get_packages(pkg.name)
                if local:
                    renderable.append_text(
                        Text(
                            f"(Installed: {pkg.version}) ",
                            style="bright_green",
                        )
                    )

            elif isinstance(pkg, AURBasic):
                renderable.append_text(
                    Text(f"(+{get_votes(pkg)} {get_popularity(pkg)}) ")
                )
                local = self.localdb.get_packages(pkg.name)
                if local:
                    renderable.append_text(
                        Text(
                            f"(Installed: {pkg.version}) ",
                            style="bright_green",
                        )
                    )
                renderable.append_text(get_orphan(pkg))
                renderable.append_text(get_flag_date(pkg))

            if include_num is True:
                num = Text(f"{num} ")
                num.stylize("magenta", 0, len(num))
                num.append_text(renderable)
                renderable = num

            if pkg.desc:
                renderable = Text("\n    ").join([renderable, Text(pkg.desc)])

            render_result.append(renderable)

        render_result = Group(*render_result)

        console.print(render_result)

    def print_pkginfo(self) -> None:
        """
        Print a package's meta data according to pacman (sync packages) or AURweb RPC interface info request (AUR packages)

        :param packages: A package.Package or series of package.Package objects for which to retrieve info
        :type packages: package.Package
        """
        console.print(":: Querying AUR...")

        missing = self.targets
        sync = self.sync_db.get_packages(*self.targets)
        aur = self.aur.get_packages(*self.targets)
        for pkg in sync + aur:
            if pkg.name in missing:
                missing.pop(missing.index(pkg.name))

        console.print(f"Packages not in AUR: {', '.join([pkg for pkg in missing])}")

        if sync:
            subprocess.run(
                shlex.split(f"pacman -Si {' '.join([target.name for target in sync])}")
            )

        console.print(Group(*aur))

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

        if self.download_only is True:
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
