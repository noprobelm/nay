from .sync_db import LocalDatabase, SyncDatabase
from .aur import AUR
from typing import Optional


class Manager:
    def __init__(self, root: str, dbpath: str, config: str):
        self.localdb = LocalDatabase(root, dbpath)
        self.syncdb = SyncDatabase(root, dbpath, config)
        self.aur = AUR()

    def search(self, query: str, sortby: Optional[str] = "db"):
        aur_packages = self.aur.search(query)
        sync_packages = self.syncdb.search(query)
        packages = aur_packages + sync_packages

        sort_priorities = {"db": {"core": 0, "extra": 1, "community": 2, "multilib": 4}}
        for num, db in enumerate(self.syncdb):
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

    def select_packages(self, packages: dict[int, Package]) -> list[Package]:
        """
        Select packages based on user input. Inputs can be separated by spaces
        Valid selections (any number of any combination of the below) * Must be separated by space characters:
        - int: A single selection (i.e. '1 3 5')
        - inclusive series of int: A range of selections to include (i.e. '1-3 6-9')
        - exclusive series of int: A range of selections to exclude (i.e. '^1-3 ^6-9')
        :param packages: A dictionary of integers representing index to package results
        :type packages: dict[int, Package]
        :returns: list of packages
        :rtype: list[Package]
        """

        # TODO: Add functionality for excluding packages (e.g. ^4)

        console.print(
            "[bright_green]==>[/bright_green] Packages to install (eg: 1 2 3, 1-3 or ^4)"
        )
        selections = console.input("[bright_green]==>[/bright_green] ")

        matches = re.findall(r"\^?\d+(?:-\d+)?", selections)
        selections = set()
        for match in matches:
            if "-" in match:
                start, end = match.split("-")
                if match.startswith("^"):
                    start = start.strip("^")
                    for num in range(int(start), int(end) + 1):
                        selections.discard(num)
                else:
                    for num in range(int(start), int(end) + 1):
                        selections.add(num)
            elif match.startswith("^"):
                match = match.strip("^")
                selections.discard(int(match))
            else:
                selections.add(int(match))
        selected = []
        for num in selections:
            try:
                selected.append(packages[num])

            # Ignore invalid selections by the user
            except KeyError:
                pass

        aur_query = requests.get(
            f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join([pkg.name for pkg in selected])}"
        ).json()

        # Replace AUR packages generated from search query with AUR info query
        for result in aur_query["results"]:
            pkg = AURPackage.from_info_query(result)
            selected.pop(selected.index(pkg))
            selected.append(pkg)

        return selected

    def get_packages(self, *names: str):
        sync_packages = self.syncdb.get_packages(*names)
        aur_packages = self.aur.get_packages(
            *[name for name in names if name not in sync_packages]
        )
        packages = sync_packages + aur_packages
        return packages

    def get_dependency_tree(
        self,
        *packages: Package,
        recursive: Optional[bool] = True,
    ) -> nx.DiGraph:
        """
        Get the AUR dependency tree for a package or series of packages

        :param recursive: Optional parameter indicating whether this function should run recursively. If 'False', only immediate dependencies will be returned. Defaults is True
        :type recursive: Optional[bool]

        :return: A dependency tree of all packages passed to the function
        :rtype: nx.DiGraph
        """
        tree = nx.DiGraph()
        aur_query = []

        aur_deps = {pkg: {} for pkg in packages}
        for pkg in packages:
            tree.add_node(pkg)
            for dtype in ["check_depends", "make_depends", "depends"]:
                for dep in getattr(pkg, dtype):
                    aur_query.append(dep)
                    aur_deps[pkg][dep] = {"dtype": dtype}

        aur_info = self.get_packages(*set(list(aur_query)))
        for pkg in aur_deps:
            for dep in aur_info:
                if dep.name in aur_deps[pkg].keys():
                    tree.add_edge(pkg, dep, dtype=aur_deps[pkg][dep.name]["dtype"])
        if recursive is False:
            return tree

        layers = [layer for layer in nx.bfs_layers(tree, packages)]
        if len(layers) > 1:
            dependencies = layers[1]
            tree = nx.compose(tree, self.get_dependency_tree(*dependencies))

        return tree

    def get_depends(self, *packages: Package) -> dict[str, list[Package]]:
        sync_depends = self.syncdb.get_depends(
            *[pkg for pkg in packages if isinstance(pkg, SyncPackage)]
        )
        aur_depends = self.aur.get_depends(
            *[pkg for pkg in packages if isinstance(pkg, AURPackage)]
        )

        return {"sync": sync_depends, "aur": aur_depends}

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

    def print_pkginfo(self, *packages: Package) -> None:
        """
        Print a package's meta data according to pacman (sync packages) or AURweb RPC interface info request (AUR packages)

        :param packages: A package.Package or series of package.Package objects for which to retrieve info
        :type packages: package.Package
        """
        aur = []
        sync = []
        for pkg in packages:
            if isinstance(pkg, AURPackage):
                aur.append(pkg.info)
            else:
                sync.append(pkg)

        aur = Group(*aur)

        if sync:
            subprocess.run(
                shlex.split(f"pacman -Si {' '.join([pkg.name for pkg in sync])}")
            )

        console.print(aur)
