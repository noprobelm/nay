import os
import datetime
from .config import CACHEDIR
from .package import AURBasic, AURPackage, Package
import shutil
from typing import Optional
import subprocess
import shlex
import requests
import networkx as nx
from .console import NayConsole


class AUR:
    def __init__(self, local: "pyalpm.Database"):
        self.local = local
        self.console = NayConsole()
        self.search_endpoint = "https://aur.archlinux.org/rpc/?v=5&type=search&arg="
        self.info_endpoint = "https://aur.archlinux.org/rpc/?v=5&type=info&arg[]="

    def search(self, query):
        packages = []

        results = requests.get(
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

        results = requests.get(
            f"{self.info_endpoint}&arg[]={'&arg[]='.join(names)}"
        ).json()
        for result in results["results"]:
            if names.count(result["Name"]) == 0:
                missing.append(result["Name"])
            packages.append(AURPackage.from_info_query(result))

        if missing and verbose is True:
            self.console.print(
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
        tree = nx.DiGraph()
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

        layers = [layer for layer in nx.bfs_layers(tree, packages)]
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

    def install(
        self,
        *packages: AURPackage,
        pacman_params: list,
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

        from .utils import makepkg

        targets = []
        for pkg in packages:
            if pacman_params.count("--nodeps") > 1:
                makepkg(pkg, CACHEDIR, "fscd")
            else:
                makepkg(pkg, CACHEDIR, "fsc")

            pattern = f"{pkg.name}-"
            for obj in os.listdir(os.path.join(CACHEDIR, pkg.name)):
                if pattern in obj and obj.endswith("zst"):
                    targets.append(os.path.join(CACHEDIR, pkg.name, obj))

        subprocess.run(
            shlex.split(f"sudo pacman {' '.join(pacman_params)} {' '.join(targets)}")
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

    def get_pkgbuild(
        self, pkg: Package, clonedir: Optional[str] = CACHEDIR, force=False
    ) -> None:
        """
        Get the PKGBUILD file from package.Package data

        :param pkg: The package.Package object to get the PKGBUILD for
        :type pkg: package.Package
        :param pkgdir: Optional directory to clone the PKGBUILD to. Default is 'None'
        :type pkgdir: Optional[str]

        """

        if not clonedir:
            clonedir = os.path.join(os.getcwd(), pkg.name)
        else:
            clonedir = os.path.join(clonedir, pkg.name)
        if force:
            shutil.rmtree(clonedir, ignore_errors=True)

        subprocess.run(
            shlex.split(
                f"git clone https://aur.archlinux.org/{pkg.name}.git {clonedir}"
            ),
            capture_output=True,
        )

    def refresh(self, force=False):
        def get_cache():
            response = requests.get("https://aur.archlinux.org/packages.gz")
            content = response.content.decode().strip()
            with open(os.path.join(CACHEDIR, "aur.cache"), "w") as f:
                f.write(content)

        aur_cache = os.path.join(CACHEDIR, "aur.cache")
        try:
            last_modified = datetime.datetime.now() - datetime.datetime.fromtimestamp(
                os.path.getmtime(aur_cache)
            )
        except FileNotFoundError:
            get_cache()
            return

        if force is True or last_modified.days >= 5:
            get_cache()

    def list(self):
        response = requests.get("https://aur.archlinux.org/packages.gz")
        packages = response.content.decode().strip().split("\n")

        # Rich takes too long to render these data. Might work to find a workaround in the future.
        for pkg in packages:
            installed = False
            if self.local.get_pkg(pkg):
                installed = True
            pkg = f"\u001b[34;1maur\033[0m {pkg}\033[92m unknown-version\033[0m"
            if installed is True:
                pkg = f"{pkg} \033[96m[installed]\033[0m"
            print(pkg)
