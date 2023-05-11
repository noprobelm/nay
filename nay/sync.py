from nay.operations import Operation
import subprocess
import shlex
from nay.utils import clean_cachedir, clean_untracked
from nay.exceptions import MissingTargets
from typing import Optional
from dataclasses import dataclass
from rich.console import Group
from rich.text import Text
from .package import Package, SyncPackage, AURPackage, AURBasic
from rich.table import Table, Column
import networkx as nx
import concurrent.futures
from .utils import get_pkgbuild


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
            params = self.wrapper_params + ["--refresh" for _ in range(self.refresh)]
            self.wrap_pacman(params, sudo=True)

        if self.sysupgrade is True:
            params = self.wrapper_params + ["--sysupgrade"]
            self.wrap_pacman(params, sudo=True)
            if not self.targets:
                return

        if self.clean:
            params = self.wrapper_params + ["--clean" for _ in range(self.clean)]
            self.clean_pkgcache()
            return

        if self.search is True:
            if not self.targets:
                params = self.wrapper_params + ["--search"]
                self.wrap_pacman(params, sudo=False)
                return

            packages = self.search_packages(" ".join(self.targets))
            self.console.print_packages(packages, self.local, include_num=False)
            return

        if self.info is True:
            if not self.targets:
                params = [
                    "--sync",
                    "--info",
                ]
                self.wrap_pacman(params, sudo=False)
            else:
                self.print_pkginfo()

            return

        if not self.targets:
            raise MissingTargets("error: no targets specified (use -h for help)")

        sync_explicit = self.sync_db.get_packages(*self.targets)
        aur_explicit = self.aur.get_packages(*self.targets)

        self.install(sync_explicit, aur_explicit)

    def clean_pkgcache(self) -> None:
        if self.console.prompt(
            message="Do you want to remove all other AUR packages from cache? [Y/n]",
            affirm="y",
        ):
            self.console.notify("removing untracked AUR files from cache...")
            self.aur.clean_cachedir()

        if self.console.prompt(
            message="Do you want to remove ALL untracked AUR files? [Y/n]", affirm="y"
        ):
            self.aur.clean_untracked()

    def search_packages(
        self, query: str, sortby: Optional[str] = "db"
    ) -> dict[int, Package]:
        def search():
            packages = []
            for db in self.sync:
                packages.extend(
                    [
                        SyncPackage.from_pyalpm(pkg)
                        for pkg in self.sync[db].search(query)
                    ]
                )
            packages.extend(self.aur.search(query))
            return packages

        def sort_packages(packages):
            sort_priorities = {
                "db": {"core": 0, "extra": 1, "community": 2, "multilib": 4}
            }
            for num, db in enumerate(self.sync):
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

        packages = search()
        packages = sort_packages(packages)
        return packages

    def print_pkginfo(self) -> None:
        """
        Print a package's meta data according to pacman (sync packages) or AURweb RPC interface info request (AUR packages)

        :param packages: A package.Package or series of package.Package objects for which to retrieve info
        :type packages: package.Package
        """
        self.console.notify(":: Querying AUR...")

        missing = list(self.targets)
        sync = []
        aur = []
        for db in self.sync:
            for target in self.targets:
                if self.sync[db].get_pkg(target):
                    sync.append(target)
                    missing.pop(missing.index(target))
        aur = self.aur.get_packages(*self.targets)
        for pkg in aur:
            if pkg.name in missing:
                missing.pop(missing.index(pkg.name))

        self.console.alert(
            f"Packages not in AUR: {', '.join([pkg for pkg in missing])}"
        )

        if sync:
            params = self.wrapper_params + ["--info", f"{' '.join(sync)}"]
            self.wrap_pacman(params, sudo=False)

        self.console.print_pkginfo(*aur)

    def install(
        self, sync_explicit: list[SyncPackage], aur_explicit: list[AURPackage]
    ) -> None:
        def preview_packages(
            sync_explicit: Optional[list[SyncPackage]] = None,
            sync_depends: Optional[list[SyncPackage]] = None,
            aur_explicit: Optional[list[AURPackage]] = None,
            aur_depends: Optional[list[AURPackage]] = None,
        ) -> None:
            """
            Print a list of packages to be installed to the terminal

            :param sync_explicit: A list of SyncPackage objects to be explicitly installed
            :type sync_explicit: list[SyncPackage]
            :param sync_depends: A list of SyncPackage dependencies to be installed
            :type sync_depends: list[SyncPackage]
            :param aur_explicit: An list of AURPackage objects to be explicitly installed
            :type aur_explicit: list[AURPackage]
            :param aur_depends: A list of AURPackage dependencies to be installed
            :type aur_depends: list[AURPackage]
            """

            if sync_explicit:
                output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in sync_explicit]
                console.print(
                    f"Sync Explicit {len(sync_explicit)}: {', '.join([pkg for pkg in output])}"
                )
            if aur_explicit:
                output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in aur_explicit]
                console.print(
                    f"AUR Explicit ({len(aur_explicit)}): {', '.join([pkg for pkg in output])}"
                )

            if aur_depends:
                output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in aur_depends]
                console.print(
                    f"AUR Dependency ({len(aur_depends)}): {', '.join([out for out in output])}"
                )

            if sync_depends:
                output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in sync_depends]
                console.print(
                    f"Sync Dependency ({len(sync_depends)}): {', '.join([out for out in output])}"
                )

        def get_missing_pkgbuild(
            *packages: AURPackage, multithread=True, verbose=False
        ) -> None:
            """
            Get missing PKGBUILD files

            :param packages: An AURPackage or series of AURPackage objects to get PKGBUILD data for
            :type packages: AURPackage
            :param multithread: Optional parameter indicating whether this function should be multithreaded. Default is True
            :type multithread: Optional[bool]
            :param verbose: Optional parameter indicating whether success/failure messages should be verbose. Default is False
            :type verbose: Optional[bool]
            """
            missing = []
            for pkg in packages:
                if not pkg.pkgbuild_exists:
                    missing.append(pkg)
                else:
                    if verbose:
                        console.print(
                            f"[notify]::[/notify] PKGBUILD up to date, skipping download: [notify]{pkg.name}"
                        )

            if multithread:
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    for num, pkg in enumerate(missing):
                        executor.submit(get_pkgbuild, pkg, force=True)
                        if verbose:
                            console.print(
                                f"[notify]::[/notify] ({num+1}/{len(missing)}) Downloaded PKGBUILD: [notify]{pkg.name}"
                            )
            else:
                for num, pkg in enumerate(missing):
                    get_pkgbuild(pkg, force=True)
                    if verbose:
                        console.print(
                            f"[notify]::[/notify] {num+1}/{len(missing)} Downloaded PKGBUILD: [notify]{pkg.name}"
                        )

        def preview_aur(*packages: AURPackage) -> None:
            """
            Print an overview of the explicit and depends AUR packages to be installed

            :param packages: A package or series of AURPackage objects to be explicitly installed
            :type packages: package.AURPackage
            """

            install_preview = Table.grid(
                Column("num", justify="right"),
                Column("pkgname", width=35, justify="left"),
                Column("pkgbuild_exists"),
                padding=(0, 1, 0, 1),
            )

            for num, pkg in enumerate(packages):
                # TODO: Fix hardcoded "Build Files Exist" -- I'm not how we'd encounter a scenario where we got here and they don't already exist
                install_preview.add_row(
                    f"[magenta]{len(packages) - num}[/magenta]",
                    pkg.name,
                    "[bright_green](Build Files Exist)",
                )

            console.print(install_preview)

        def prompt_proceed() -> None:
            """Present prompt to proceed with installation"""
            prompt = console.input(
                "[bright_green]==>[/bright_green] Install packages? [Y/n] "
            )
            if not prompt.lower().startswith("y"):
                quit()

        pacman_flags = ["--sync"]
        pacman_flags.extend(["--nodeps" for _ in range(self.nodeps)])
        if self.download_only:
            pacman_flags.append("--downloadonly")
        skip_verchecks = True if self.nodeps > 0 else False
        skip_depchecks = True if self.nodeps > 1 else False
        download_only = self.download_only

        for _ in range(self.nodeps):
            pacman_flags.append("--nodeps")
        if download_only is True:
            pacman_flags.append("--downloadonly")

        pacman_flags.extend([pkg.name for pkg in sync_explicit])

        if skip_depchecks is True:
            preview_packages(sync_explicit=sync_explicit, aur_explicit=aur_explicit)
            if aur_explicit:
                get_missing_pkgbuild(*aur_explicit, verbose=True)
                preview_aur(*aur_explicit)
                prompt_proceed()
                self.aur.install(*aur_explicit)
            if sync_explicit:
                self.wrap_pacman(pacman_flags, sudo=True)

        aur_tree = self.aur.get_dependency_tree(*aur_explicit, recursive=False)
        aur_depends = list(
            filter(
                lambda x: not self.local_db.get_packages(x.name),
                [dep for pkg, dep in aur_tree.edges],
            )
        )
        sync_depends = list(
            filter(
                lambda x: not self.local_db.get_packages(x.name),
                [dep for dep in self.sync_db.get_depends(*aur_explicit)],
            )
        )
        print([dep.name for dep in sync_depends])
        quit()
        get_missing_pkgbuild(*[node for node in aur_tree.nodes], verbose=True)
        preview_packages(
            sync_explicit=sync_explicit,
            sync_depends=sync_depends,
            aur_explicit=aur_explicit,
            aur_depends=aur_depends,
        )
        preview_aur(*[node for node in aur_tree.nodes])
        prompt_proceed()
        if aur_depends:
            aur_tree = nx.compose(aur_tree, self.aur.get_dependency_tree(*aur_depends))
        get_missing_pkgbuild(*[node for node in aur_tree], verbose=False)
        if aur_tree:
            install_order = [layer for layer in nx.bfs_layers(aur_tree, aur_explicit)][
                ::-1
            ]
            for num, layer in enumerate(install_order):
                if num + 1 == len(install_order):
                    self.aur.install(*layer, download_only=download_only, asdeps=False)
                else:
                    self.aur.install(*layer, download_only=download_only, asdeps=True)
        if sync_explicit:
            self.wrap_pacman(pacman_flags, sudo=True)
