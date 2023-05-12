import os
from .config import CACHEDIR
from .package import AURBasic, AURPackage, Package
import shutil
from typing import Optional
from .utils import makepkg
import subprocess
import shlex


class AUR:
    def __init__(self, syncdb: "pyalpm.Database", localdb: "pyalpm.Database"):
        import requests
        import networkx as nx

        self.requests = requests
        self.nx = nx
        self.syncdb = syncdb
        self.localdb = localdb
        self.search_endpoint = "https://aur.archlinux.org/rpc/?v=5&type=search&arg="
        self.info_endpoint = "https://aur.archlinux.org/rpc/?v=5&type=info&arg[]="

    def search(self, query):
        packages = []

        results = self.requests.get(
            f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={query}"
        ).json()

        if results["results"]:
            packages.extend(
                AURBasic.from_search_query(result) for result in results["results"]
            )

        return packages

    def get_packages(self, *names, verbose=False):
        packages = []
        missing = []
        names = list(set(names))

        results = self.requests.get(
            f"{self.info_endpoint}&arg[]={'&arg[]='.join(names)}"
        ).json()
        for result in results["results"]:
            if names.count(result["Name"]) == 0:
                missing.append(result["Name"])
            packages.append(AURPackage.from_info_query(result))

        if missing and verbose is True:
            console.print(
                f"[red]->[/red] No AUR package found for {', '.join(missing)}"
            )

        return packages

    def get_dependency_tree(
        self,
        *packages: AURPackage,
        recursive: Optional[bool] = True,
    ) -> "nx.DiGraph":
        """
        Get the AUR dependency tree for a package or series of packages

        :param recursive: Optional parameter indicating whether this function should run recursively. If 'False', only immediate dependencies will be returned. Defaults is True
        :type recursive: Optional[bool]

        :return: A dependency tree of all packages passed to the function
        :rtype: nx.DiGraph
        """
        tree = self.nx.DiGraph()
        aur_query = []

        aur_deps = {pkg: {} for pkg in packages}
        for pkg in packages:
            tree.add_node(pkg)
            for dtype in ["check_depends", "make_depends", "depends"]:
                for dep_name in getattr(pkg, dtype):
                    aur_query.append(dep_name)
                    aur_deps[pkg][dep_name] = {"dtype": dtype}

        aur_info = self.get_packages(*set(list(aur_query)))
        for pkg in aur_deps:
            for dep in aur_info:
                if dep.name in aur_deps[pkg].keys():
                    tree.add_edge(pkg, dep, dtype=aur_deps[pkg][dep.name]["dtype"])

        if recursive is False:
            return tree

        layers = [layer for layer in self.nx.bfs_layers(tree, packages)]
        if len(layers) > 1:
            dependencies = layers[1]
            tree = self.nx.compose(tree, self.get_dependency_tree(*dependencies))

        return tree

    def get_depends(self, aur_tree: "nx.DiGraph") -> list[Package]:
        """
        Get the aur dependencies from installation targets

        :param aur_tree: The dependency tree of the AUR explicit packages
        :type aur_tree: nx.DiGraph
        :param skip_verchecks: Flag to skip version checks for dependencies. Default is False
        :type skip_verchecks: bool

        :return: A list of the aur dependencies
        :rtype: list[AurPackage]
        """

        aur_depends = []
        for pkg, dep in aur_tree.edges:
            if aur_tree.get_edge_data(pkg, dep)["dtype"] != "opt_depends":
                aur_depends.append(dep)

        return aur_depends

    def clean_cachedir(self) -> None:
        os.chdir(CACHEDIR)
        for obj in os.listdir():
            shutil.rmtree(obj, ignore_errors=True)

    def clean_untracked(self) -> None:
        os.chdir(CACHEDIR)
        for obj in os.listdir():
            if os.path.isdir(os.path.join(os.getcwd(), obj)):
                os.chdir(os.path.join(os.getcwd(), obj))
                for _ in os.listdir():
                    if _.endswith(".tar.zst"):
                        os.remove(_)
                os.chdir("../")

    def install(
        self,
        *packages: AURPackage,
        skip_depchecks: Optional[bool] = False,
        download_only: Optional[bool] = False,
        asdeps: Optional[bool] = False,
    ):
        """
        Install passed AURPackage objects

        :param packages: Package or series of packages to install
        :type packages: AURPackage
        :param skip_depchecks: Flag to skip dependency checks. Default is False
        :type skip_depchecks: bool
        :param download_only: Flag download only (makepkg will still occur, packages will not be installed)
        :type download_only bool
        """
        targets = []
        for pkg in packages:
            if skip_depchecks is True:
                makepkg(pkg, CACHEDIR, "fscd")
            else:
                makepkg(pkg, CACHEDIR, "fsc")

            pattern = f"{pkg.name}-"
            for obj in os.listdir(os.path.join(CACHEDIR, pkg.name)):
                print(obj)
                if pattern in obj and obj.endswith("zst"):
                    targets.append(os.path.join(CACHEDIR, pkg.name, obj))

        if download_only is False:
            if asdeps is True:
                subprocess.run(
                    shlex.split(f"sudo pacman -U --asdeps {' '.join(targets)}")
                )
            else:
                subprocess.run(shlex.split(f"sudo pacman -U {' '.join(targets)}"))

        else:
            console.print(
                f"-> nothing to install for {' '.join([target for target in targets])}"
            )

    def clean_cachedir(self) -> None:
        """
        Clean the cachedir
        """
        os.chdir(CACHEDIR)
        for obj in os.listdir():
            shutil.rmtree(obj, ignore_errors=True)

    def clean_untracked(self) -> None:
        """
        Clean package metadata out of cached package directories
        """
        os.chdir(CACHEDIR)
        for obj in os.listdir():
            if os.path.isdir(os.path.join(os.getcwd(), obj)):
                os.chdir(os.path.join(os.getcwd(), obj))
                for _ in os.listdir():
                    if _.endswith(".tar.zst"):
                        os.remove(_)
                os.chdir("../")
