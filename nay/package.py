import os
import re
from datetime import datetime
from typing import Optional

import networkx as nx
import pyalpm
import requests
from rich.table import Column, Table
from .config import CACHEDIR


class Package:
    """
    A minimum representation of an Arch package, agnostic to its origin (Sync vs AUR)

    :param db: The database name where the package is located ('core', 'multilib', 'aur'...)
    :type db: str
    :param name: The name of the package
    :type name: str
    :param version: The package version
    :type version: str
    :param desc: The description of the package
    :type desc: str

    :ivar db: The database name where the package is located
    :ivar name: The name of the package
    :ivar version: The version number of the package
    :ivar desc: The description of the package
    """

    def __init__(
        self,
        db: str,
        name: str,
        version: str,
        desc: str,
        check_depends: Optional[list[str]] = [],
        make_depends: Optional[list[str]] = [],
        depends: Optional[list[str]] = [],
        opt_depends: Optional[list[str]] = [],
    ) -> None:
        self.db = db
        self.name = name
        self.version = version
        self.desc = desc
        self.check_depends = check_depends
        self.make_depends = make_depends
        self.depends = depends
        self.opt_depends = opt_depends

    @property
    def dependencies(self):
        dependencies = []
        for dtype in ["check_depends, make_depence, depends", "opt_depends"]:
            dependencies.extend(getattr(self, dtype))

        return dependencies

    def __lt__(self, other) -> bool:
        """
        Compare two `Package` instances for alphabetical sorting purposes

        :param other: The `Package` object to compare for sorting
        :type other: Package

        :return: A boolean indicating where the db var falls alphabetically
        :rtype: bool
        """
        if isinstance(other, Package):
            if self.db < other.db:
                return True
            elif self.db == other.db and self.name < other.name:
                return True

        return False

    def __hash__(self) -> int:
        """
        Generate a hash value for this `Package` instance. This is primarily used for locating Package instances among an nx.DiGraph object.

        :return: A hash value of the package name and version
        :rtype: int
        """
        return hash(self.name)

    def __eq__(self, other) -> bool:
        """
        Compare two `Package` instances and determine if they are equal. This is primarily used for locating Package instances among an nx.DiGraph object.

        :param other: The `Package` object to compare.
        :type other: Package

        :return: A boolean indicating whether the two instances are equal.
        :rtype: bool
        """
        if not isinstance(other, Package):
            return False

        return hash((self.name, self.version)) == hash((other.name, other.version))


class SyncPackage(Package):
    """
    A representation of an Arch package sourced from a synchronization database

    :param db: The sync database name where the package is located ('core', 'multilib')
    :type db: str
    :param name: The name of the package
    :type name: str
    :param version: The package version
    :type version: str
    :param desc: The description of the package
    :type desc: str
    :param size: The size of the package in bytes
    :type size: int
    :param isize: The installed size of the package in bytes
    :type isize: int

    :ivar db: The sync database name where the package is located ('core', 'multilib')
    :ivar name: The name of the package
    :ivar version: The package version
    :ivar desc: The description of the package
    :ivar size: The size of the package in bytes
    :ivar isize: The installed size of the package in bytes

    """

    def __init__(
        self,
        db: str,
        name: str,
        version: str,
        desc: str,
        check_depends: Optional[list[str]],
        make_depends: Optional[list[str]],
        depends: Optional[list[str]],
        opt_depends: Optional[list[str]],
        size: int,
        isize: int,
    ) -> None:
        super().__init__(
            db, name, version, desc, check_depends, make_depends, depends, opt_depends
        )
        self.size = self.format_bytes(size)
        self.isize = self.format_bytes(isize)

    @classmethod
    def from_pyalpm(cls, pkg: pyalpm.Package) -> "SyncPackage":
        """
        Create a `SyncPackage` instance from a `pyalpm.Package` instance.

        :param pkg: The `pyalpm.Package` instance to create the `SyncPackage` from.
        :type pkg: pyalpm.Package

        :return: A `SyncPackage` instance.
        :rtype: SyncPackage
        """
        kwargs = {
            "name": pkg.name,
            "version": pkg.version,
            "desc": pkg.desc,
            "db": pkg.db.name,
            "check_depends": pkg.checkdepends,
            "make_depends": pkg.makedepends,
            "opt_depends": pkg.optdepends,
            "depends": pkg.depends,
            "size": pkg.size,
            "isize": pkg.isize,
        }
        return cls(**kwargs)

    @staticmethod
    def format_bytes(size) -> str:
        """
        Format a size value to human-readable format

        :param size: The size value to format
        :type size: int

        :return: A human-readable size value
        :rtype: str
        """

        # TODO: Fix calculations for Kebi/Mebi vs KB/MB. These are not the same
        power = 2**10
        n = 0
        power_labels = {0: "B", 1: "KiB", 2: "MiB", 3: "GiB", 4: "TiB"}
        while size > power:
            size /= power
            n += 1
        return f"{round(size, 1)} {power_labels[n]}"


class AURBasic(Package):
    def __init__(
        self,
        db: str,
        name: str,
        version: str,
        desc: str,
        votes: int,
        popularity: int,
        flag_date: Optional[int] = None,
        orphaned: Optional[int] = False,
        search_query: Optional[dict] = None,
        check_depends: Optional[list[str]] = [],
        make_depends: Optional[list[str]] = [],
        depends: Optional[list[str]] = [],
        opt_depends: Optional[list[str]] = [],
    ) -> None:
        super().__init__(
            db, name, version, desc, check_depends, make_depends, depends, opt_depends
        )
        self.votes = votes
        self.popularity = popularity
        self.flag_date = (
            datetime.fromtimestamp(flag_date) if flag_date is not None else None
        )
        self.orphaned = orphaned
        self.search_query = search_query

    @classmethod
    def from_search_query(cls, result: dict) -> "AURSearch":
        """
        Create a `AURPackage` instance from a __search__ AURweb RPC interface HTTP request (read: https://wiki.archlinux.org/title/Aurweb_RPC_interface)

        :param result: The JSON data containing the package information
        :type dict:

        :return: An `AURPackage` instance.
        :rtype: AURPackage
        """

        kwargs = {
            "db": "aur",
            "name": result["Name"],
            "version": result["Version"],
            "desc": result["Description"] if result["Description"] else "",
            "flag_date": result["OutOfDate"],
            "orphaned": True if result["Maintainer"] is None else False,
            "votes": result["NumVotes"],
            "popularity": result["Popularity"],
        }
        return cls(**kwargs)

    @property
    def PKGBUILD(self) -> str:
        """
        Get the pseudo PKGBUILD path for a package in nay's CACHEDIR (whether it exists on the local filesystem or not)

        :return: str path to the PKGBUILD file
        :rtype: str
        """
        return os.path.join(CACHEDIR, f"{self.name}/PKGBUILD")

    @property
    def SRCINFO(self) -> str:
        """
        Get the pseudo .SRCINFO path for a package in nay's CACHEDIR (whether it exists on the local filesystem or not)

        :return: str path to the .SRCINFO file
        :rtype: str
        """
        return os.path.join(CACHEDIR, f"{self.name}/.SRCINFO")

    @property
    def pkgbuild_exists(self) -> bool:
        """
        Check if the PKGBUILD file exists. This will return 'False' if the PKGBUILD exists but is mismatched with the class instance's version

        :return: bool: True if PKGBUILD exists and is up to date; False if PKGBUILD exists and is out of date or does not exist
        :rtype: bool
        """

        if os.path.exists(self.PKGBUILD):
            try:
                with open(self.SRCINFO, "r") as f:
                    if re.search(r"pkgver=(.*)", f.read()) != self.version:
                        return True
                    else:
                        return False
            except FileNotFoundError:
                return False
        else:
            return False


class AURPackage(AURBasic):
    """
    A representation of an Arch package sourced from the AUR

    :param db: The sync database name where the package is located (i.e. 'aur')
    :type db: str
    :param name: The name of the package
    :type name: str
    :param version: The package version
    :type version: str
    :param desc: The description of the package
    :type desc: str
    :param votes: The number of votes on the package
    :type votes: int
    :param popularity: The popularity score of the package
    :type popularity: float
    :param flag_date: An optional int representing the epoch that the package was flagged as out-of-date (if present)
    :type flag_date: Optional[int]
    :param orphaned: An optional boolean indicating whether or not the package is an orphan
    :type orphaned: Optional[bool]
    :param make_depends: An optional list of strings representing the make dependencies of the package
    :type make_depends: Optional[List[str]]
    :param check_depends: An optional list of strings representing the check dependencies of the package
    :type check_depends: Optional[List[str]]
    :param depends: An optional list of strings representing the runtime dependencies of the package
    :type depends: Optional[List[str]]
    :param opt_depends: An optional list of strings representing the optional dependencies of the package
    :type opt_depends: Optional[List[str]]
    :param info_query: An optional dictionary containing the package's info query from the Aurweb RPC interface (read: https://wiki.archlinux.org/title/Aurweb_RPC_interface)
    :type info_query: Optional[dict]

    :ivar db: The sync database name where the package is located (i.e. 'aur')
    :ivar name: The name of the package
    :ivar version: The package version
    :ivar desc: The description of the package
    :ivar votes: The number of votes on the package
    :ivar popularity: The popularity score of the package
    :ivar flag_date: An optional int representing the epoch that the package was flagged as out-of-date (if present)
    :ivar orphaned: An optional boolean indicating whether or not the package is an orphan
    :ivar make_depends: An optional list of strings representing the make dependencies of the package
    :ivar check_depends: An optional list of strings representing the check dependencies of the package
    :ivar depends: An optional list of strings representing the runtime dependencies of the package
    :ivar opt_depends: An optional list of strings representing the optional dependencies of the package
    :ivar info_query: An optional dictionary containing the package's info query from the Aurweb RPC interface (read: https://wiki.archlinux.org/title/Aurweb_RPC_interface)

    """

    def __init__(
        self,
        db: str,
        name: str,
        version: str,
        desc: str,
        check_depends: list[str],
        make_depends: list[str],
        depends: list[str],
        opt_depends: list[str],
        votes: int,
        popularity: int,
        flag_date: Optional[int] = None,
        orphaned: Optional[int] = False,
        info_query: Optional[dict] = None,
    ) -> None:
        super().__init__(
            db,
            name,
            version,
            desc,
            votes,
            popularity,
            flag_date,
            orphaned,
            check_depends,
            make_depends,
            depends,
            opt_depends,
        )
        self.votes = votes
        self.popularity = popularity
        self.flag_date = (
            datetime.fromtimestamp(flag_date) if flag_date is not None else None
        )
        self.orphaned = orphaned
        self.info_query = info_query

    @classmethod
    def from_info_query(cls, result: dict) -> "AURPackage":
        """
        Create a `AURPackage` instance from an __info__ AURweb RPC interface HTTP request (read: https://wiki.archlinux.org/title/Aurweb_RPC_interface)

        :param result: The JSON data containing the package information
        :type dict:

        :return: An `AURPackage` instance.
        :rtype: AURPackage
        """

        kwargs = {
            "db": "aur",
            "name": result["Name"],
            "version": result["Version"],
            "desc": result["Description"],
            "flag_date": result["OutOfDate"],
            "orphaned": True if result["Maintainer"] is None else False,
            "votes": result["NumVotes"],
            "popularity": result["Popularity"],
            "info_query": result,
        }

        dep_types = {
            "MakeDepends": "make_depends",
            "CheckDepends": "check_depends",
            "Depends": "depends",
            "OptDepends": "opt_depends",
        }
        for dtype in dep_types.keys():
            if dtype in result.keys():
                kwargs[dep_types[dtype]] = result[dtype]
            else:
                kwargs[dep_types[dtype]] = None

        return cls(**kwargs)

    def get_dependency_tree(self) -> nx.DiGraph:
        """
        Get the dependency tree of the AUR represented as a networkx DiGraph object. This method will return a graph of __only__ the immediate dependencies

        :return: A dependency tree
        :rtype: nx.DiGraph
        """

        tree = nx.DiGraph()
        tree.add_node(self)
        dtypes = ["check_depends", "make_depends", "depends"]
        all_depends = []
        sync_depends = []
        aur_depends = []
        for dtype in dtypes:
            deps = getattr(self, dtype)
            if isinstance(deps, list):
                all_depends += list(set(deps))
        for dep in all_depends:
            if dep in SYNC_PACKAGES:
                sync_depends.append(dep)
            else:
                aur_depends.append(dep)
        if aur_depends:
            aur_query = requests.get(
                f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join(all_depends)}"
            ).json()
            if aur_query["results"]:
                for result in aur_query["results"]:
                    dep = AURPackage.from_info_query(result)
                    for dtype in dtypes:
                        deps = getattr(self, dtype)
                        if isinstance(deps, list) and dep.name in deps:
                            tree.add_edge(self, dep, dtype=dtype)
        return tree

    @property
    def info(self) -> Table:
        """
        Get the information on the AUR package in a table format (analogous to the output of pacman -Si <pkg>)

        :return: A table containing package information
        :rtype: rich.table.Table
        """

        if not self.info_query:
            query = requests.get(
                f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={self.name}"
            ).json()
            self.info_query = query["results"][0]

        grid = Table.grid(Column("field", width=30), Column("value"))
        grid.add_row("Repository", ": aur")
        grid.add_row("Name", f": {self.info_query['Name']}")
        grid.add_row(
            "Keywords",
            f": {self.info_query['Keywords'] if self.info_query['Keywords'] else None}",
        )
        grid.add_row("Version", f": {self.info_query['Version']}")
        grid.add_row("Description", f": {self.info_query['Description']}")
        grid.add_row("URL", f": {self.info_query['URL']}")
        grid.add_row("AUR URL", f": https://aur.archlinux.org/packages/{self.name}")
        # TODO: Fix hardcoded 'None'
        grid.add_row("Groups", ": None")
        grid.add_row(
            "License", f": {'  '.join([_ for _ in self.info_query['License']])}"
        )
        grid.add_row(
            "Provides", f": {'  '.join([pkg for pkg in self.info_query['Provides']])}"
        )
        grid.add_row(
            "Depends On",
            f": {'  '.join([pkg for pkg in self.info_query['Depends']])}",
        )
        grid.add_row(
            "Make Deps",
            f": {'  '.join([pkg for pkg in self.info_query['MakeDepends']])}",
        )
        # TODO: Fix hardcoded 'None'
        grid.add_row("Check Deps", ": None")
        # TODO: Fix hardcoded 'None'
        grid.add_row("Optional Deps", ": None")
        # TODO: Fix hardcoded 'None'
        grid.add_row("Conflicts With", ": None")
        grid.add_row("Maintainer", f": {self.info_query['Maintainer']}")
        grid.add_row("Votes", f": {self.info_query['NumVotes']}")
        grid.add_row("Popularity", f": {self.info_query['Popularity']}")
        grid.add_row(
            "First Submitted",
            f": {datetime.fromtimestamp(self.info_query['FirstSubmitted']).strftime('%s %d %b %Y %I:%M:%S %p %Z')}",
        )
        grid.add_row(
            "Last Modified",
            f": {datetime.fromtimestamp(self.info_query['LastModified']).strftime('%s %d %b %Y %I:%M:%S %p %Z')}",
        )

        return grid
