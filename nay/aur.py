import requests
import os
from .config import CACHEDIR
from .package import AURBasic, AURPackage, Package
from .console import console
import shutil
import networkx as nx


class AUR:
    def __init__(self):
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
        names = list(names)

        results = requests.get(
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

    def get_depends(self, aur_tree: nx.DiGraph) -> list[Package]:
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
