from nay.operations import Operation
from nay.exceptions import MissingTargets
from typing import Optional
from dataclasses import dataclass
from .package import Package, SyncPackage, AURPackage, AURBasic
from rich.table import Table, Column
import networkx as nx
import concurrent.futures
import subprocess
import shlex


@dataclass
class Sync(Operation):
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
        if "--refresh" in self.pacman_params:
            refresh = ["--refresh" for _ in range(self.refresh)]
            params = self.db_params + refresh
            self.wrap_sync(params, sudo=True)
            self.pacman_params = list(
                filter(lambda x: x != "--refresh", self.pacman_params)
            )
            force = False
            if len(refresh) > 1:
                force = True
            self.aur.refresh(force=force)

            if not self.targets:
                return

        if "--sysupgrade" in self.pacman_params:
            params = self.db_params + ["--sysupgrade"]
            self.wrap_sync(params, sudo=True)
            self.pacman_params = list(
                filter(lambda x: x != "--sysupgrade", self.pacman_params)
            )

            if not self.targets:
                return

        if "--clean" in self.pacman_params:
            params = self.db_params + ["--clean" for _ in range(self.clean)]
            self.wrap_sync(params, sudo=True)
            self.clean_pkgcache()
            return

        if "--search" in self.pacman_params:
            if not self.targets:
                params = self.db_params + ["--search"]
                self.wrap_sync(params, sudo=False)
                return

            packages = self.search_packages(" ".join(self.targets))
            self.console.print_packages(packages, self.local, include_num=False)
            return

        if "--list" in self.pacman_params:
            params = self.db_params + ["--list"] + self.targets
            if "aur" in self.targets or len(self.targets) == 0:
                self.aur.list()
            self.wrap_sync(params, sudo=False)
            return

        if "--info" in self.pacman_params:
            if not self.targets:
                params = self.db_params + ["--info"]
                self.wrap_sync(params, sudo=False)
            else:
                self.print_pkginfo()

            return

        if not self.targets:
            raise MissingTargets("error: no targets specified (use -h for help)")

        self.install()

    @property
    def install_params(self):
        params = self.db_params
        for _ in range(self.nodeps):
            params.append("--nodeps")
        if self.download_only:
            params.append("--downloadonly")

    def wrap_sync(self, params: list[str], sudo: bool = False):
        prefix = "sudo " if sudo is True else ""
        subprocess.run(shlex.split(f"{prefix}pacman {' '.join([p for p in params])}"))

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
            params = self.db_params + ["--info", f"{' '.join(sync)}"]
            self.wrap_sync(params, sudo=False)

        self.console.print_pkginfo(*aur)

    def install(self, targets: Optional[list[Package]] = None) -> None:
        skip_verchecks = True if self.nodeps > 0 else False
        skip_depchecks = True if self.nodeps > 1 else False

        if targets is None:
            targets = list(set(self.targets))
            sync_explicit = []
            for db in self.sync:
                for target in targets:
                    pkg = self.sync[db].get_pkg(target)
                    if pkg:
                        sync_explicit.append(pkg)
                        targets.pop(targets.index(target))

            aur_explicit = self.aur.get_packages(*targets)
        else:
            sync_explicit = [pkg for pkg in targets if isinstance(pkg, SyncPackage)]
            aur_explicit = [pkg for pkg in targets if isinstance(pkg, AURPackage)]

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
                self.console.print(
                    f"Sync Explicit {len(sync_explicit)}: {', '.join([pkg for pkg in output])}"
                )
            if aur_explicit:
                output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in aur_explicit]
                self.console.print(
                    f"AUR Explicit ({len(aur_explicit)}): {', '.join([pkg for pkg in output])}"
                )

            if aur_depends:
                output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in aur_depends]
                self.console.print(
                    f"AUR Dependency ({len(aur_depends)}): {', '.join([out for out in output])}"
                )

            if sync_depends:
                output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in sync_depends]
                self.console.print(
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
                        self.console.notify(
                            f"PKGBUILD up to date, skipping download: [bright_cyan]{pkg.name}"
                        )

            if multithread:
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    for num, pkg in enumerate(missing):
                        executor.submit(self.aur.get_pkgbuild, pkg, force=True)
                        if verbose:
                            self.console.notify(
                                f"({num+1}/{len(missing)}) Downloaded PKGBUILD: [bright_cyan]{pkg.name}"
                            )
            else:
                for num, pkg in enumerate(missing):
                    self.aur.get_pkgbuild(pkg, force=True)
                    if verbose:
                        self.console.notify(
                            f"({num+1}/{len(missing)} Downloaded PKGBUILD: [bright_cyan]{pkg.name}"
                        )

        def print_pkgbuild_status(*packages: AURPackage) -> None:
            table = Table.grid(
                Column("num", justify="right"),
                Column("pkgname", width=35, justify="left"),
                Column("pkgbuild_exists"),
                padding=(0, 1, 0, 1),
            )

            for num, pkg in enumerate(packages):
                # TODO: Fix hardcoded "Build Files Exist" -- I'm not how we'd encounter a scenario where we got here and they don't already exist
                table.add_row(
                    f"[magenta]{len(packages) - num}[/magenta]",
                    pkg.name,
                    "[bright_green](Build Files Exist)",
                )

            self.console.print(table)

        if skip_depchecks is True:
            preview_packages(sync_explicit=sync_explicit, aur_explicit=aur_explicit)
            get_missing_pkgbuild(*aur_explicit, verbose=True)
            print_pkgbuild_status(*aur_explicit)
            if (
                self.console.prompt("Proceed with install? [Y/n]", affirm="y")
                is not True
            ):
                return

            if aur_explicit:
                self.aur.install(*aur_explicit, pacman_params=self.pacman_params)
            if sync_explicit:
                self.wrap_sync(self.pacman_params, sudo=True)

        # Dependency resolution is just a big, dirty band-aid right now. Need to add SRCINFO parsing for proper
        # fetching of sync deps

        aur_tree = self.aur.get_dependency_tree(*aur_explicit, recursive=False)
        aur_depends = self.aur.get_depends(aur_tree)
        for i, dep in enumerate(aur_depends):
            local = self.local.get_pkg(dep.name)
            if local:
                if skip_verchecks == True:
                    aur_depends.pop(i)
                elif local.version == dep.version:
                    aur_depends.pop(i)

        sync_depends = []
        for db in self.sync:
            for pkg in aur_explicit:
                for dep_type in ["make_depends", "check_depends", "depends"]:
                    deps = [dep for dep in getattr(pkg, dep_type)]
                    for dep_name in deps:
                        sync = self.sync[db].get_pkg(dep_name)
                        local = self.local.get_pkg(dep_name)
                        if sync is not None and local is None:
                            sync_depends.append(SyncPackage.from_pyalpm(sync))

        get_missing_pkgbuild(*aur_depends, verbose=True)
        preview_packages(
            sync_explicit=sync_explicit,
            sync_depends=sync_depends,
            aur_explicit=aur_explicit,
            aur_depends=aur_depends,
        )
        print_pkgbuild_status(*aur_explicit + aur_depends)

        if self.console.prompt("Proceed with install? [Y/n]", affirm="y") is not True:
            return

        if aur_depends:
            aur_tree = nx.compose(aur_tree, self.aur.get_dependency_tree(*aur_depends))

        get_missing_pkgbuild(*[node for node in aur_tree], verbose=False)
        if aur_tree:
            install_order = [layer for layer in nx.bfs_layers(aur_tree, aur_explicit)][
                ::-1
            ]
            for num, layer in enumerate(install_order):
                pacman_params = list(
                    filter(lambda x: x != "--sync", self.pacman_params)
                )
                pacman_params.append("--upgrade")
                if num + 1 == len(install_order):
                    pacman_params.append("--asdeps")

                    self.aur.install(*layer, pacman_params=pacman_params)
                else:
                    self.aur.install(*layer, pacman_params=pacman_params)
        if sync_explicit:
            pacman_params = self.pacman_params
            pacman_params.extend([pkg.name for pkg in sync_explicit])
            self.wrap_sync(pacman_params, sudo=True)


@dataclass
class Nay(Sync):
    def run(self):
        self.wrapper_prefix = "sync"
        if not self.targets:
            params = self.db_params + ["--refresh", "--sysupgrade"]
            self.wrap_sync(params, sudo=True)
            return
        packages = self.search_packages(" ".join([target for target in self.targets]))
        self.console.print_packages(packages, self.local, include_num=True)
        packages = self.select_packages(packages)
        self.install(packages)

    def select_packages(self, packages):
        selections = self.console.get_nums("Packages to install (eg: 1 2 3, 1-3 or ^4)")
        selected = []
        for num in selections:
            try:
                selected.append(packages[num])
            # Ignore invalid selections by the user
            except KeyError:
                pass

        aur_query = [pkg.name for pkg in selected if isinstance(pkg, AURBasic)]
        if aur_query:
            aur_packages = self.aur.get_packages(*aur_query)
            for num, pkg in enumerate(selected):
                for aur_pkg in aur_packages:
                    if pkg.name == aur_pkg.name:
                        selected[num] = aur_pkg

        return selected
