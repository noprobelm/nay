import os
import re
from datetime import datetime
from typing import Optional

import pyalpm

from .config import CACHEDIR


class Package:
    def __init__(
        self,
        db: str,
        name: str,
        version: str,
        desc: Optional[str] = None,
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

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Package):
            return False

        return hash((self.name, self.version)) == hash((other.name, other.version))


class SyncPackage(Package):
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
    def from_search_query(cls, result: dict) -> "AURBasic":
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

        kwargs["search_query"] = result
        return cls(**kwargs)

    @property
    def PKGBUILD(self) -> str:
        return os.path.join(CACHEDIR, f"{self.name}/PKGBUILD")

    @property
    def SRCINFO(self) -> str:
        return os.path.join(CACHEDIR, f"{self.name}/.SRCINFO")

    @property
    def pkgbuild_exists(self) -> bool:
        if os.path.exists(self.PKGBUILD):
            try:
                with open(self.SRCINFO, "r") as f:
                    data = f.read()
                pkgver = re.search(r"pkgver = (.*)", data).group(1)
                pkgrel = re.search(r"pkgrel = (.*)", data).group(1)
                epoch = re.search(r"epoch = (.*)", data)
                if epoch:
                    epoch = epoch.group(1)
                    srcinfo_ver = f"{epoch}:{pkgver}-{pkgrel}"
                else:
                    srcinfo_ver = f"{pkgver}-{pkgrel}"
                if self.version != srcinfo_ver:
                    return False

                return True
            except (FileNotFoundError, AttributeError):
                return False
        else:
            return False


class AURPackage(AURBasic):
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
        info_query: dict,
        flag_date: Optional[int] = None,
        orphaned: Optional[int] = False,
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
            check_depends=check_depends,
            make_depends=make_depends,
            depends=depends,
            opt_depends=opt_depends,
        )
        self.info_query = info_query
        self.votes = votes
        self.popularity = popularity
        self.flag_date = (
            datetime.fromtimestamp(flag_date) if flag_date is not None else None
        )
        self.orphaned = orphaned

    @classmethod
    def from_info_query(cls, result: dict) -> "AURPackage":
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
        for dtype in dep_types:
            if dtype in result.keys():
                kwargs[dep_types[dtype]] = result[dtype]
            else:
                kwargs[dep_types[dtype]] = []

        return cls(**kwargs)

    @property
    def info(self) -> "Table":
        from rich.table import Column, Table

        grid = Table.grid(Column("field", width=30), Column("value"))
        grid.add_row("Repository", ": aur")
        grid.add_row("Name", f": {self.info_query['Name']}")
        if self.info_query["Keywords"]:
            grid.add_row(
                "Keywords", f": {'  '.join([_ for _ in self.info_query['Keywords']])}"
            )
        else:
            grid.add_row("Keywords", ": None")
        grid.add_row("Version", f": {self.info_query['Version']}")
        if self.info_query["Description"]:
            grid.add_row("Description", f": {self.info_query['Description']}")
        else:
            grid.add_row("Description", ": None")
        grid.add_row("URL", f": {self.info_query['URL']}")
        grid.add_row("AUR URL", f": https://aur.archlinux.org/packages/{self.name}")
        # TODO: Fix hardcoded 'None'
        if "Groups" in self.info_query.keys():
            grid.add_row(
                "Groups", f": {'  '.join([_ for _ in self.info_query['Groups']])}"
            )
        else:
            grid.add_row("Groups", ": None")
        if "License" in self.info_query.keys():
            grid.add_row(
                "License", f": {'  '.join([_ for _ in self.info_query['License']])}"
            )
        else:
            grid.add_row("License", ": None")
        if "Provides" in self.info_query.keys():
            grid.add_row(
                "Provides",
                f": {'  '.join([pkg for pkg in self.info_query['Provides']]) if self.info_query['Provides'] else None}",
            )
        else:
            grid.add_row("Provides", ": None")
        if "Depends" in self.info_query.keys():
            grid.add_row(
                "Depends On",
                f": {'  '.join([pkg for pkg in self.info_query['Depends']])}",
            )
        else:
            grid.add_row("Depends On", ": None")
        if "MakeDepends" in self.info_query.keys():
            grid.add_row(
                "Make Deps",
                f": {'  '.join([pkg for pkg in self.info_query['MakeDepends']])}",
            )
        else:
            grid.add_row("Make Deps", ": None")
        if "CheckDepends" in self.info_query.keys():
            grid.add_row(
                "Check Deps",
                f": {'  '.join([pkg for pkg in self.info_query['CheckDepends']])}",
            )
        else:
            grid.add_row("Check Deps", ": None")
        if "OptDepends" in self.info_query.keys():
            grid.add_row(
                "Optional Deps",
                f": {'  '.join([pkg for pkg in self.info_query['OptDepends']])}",
            )
        else:
            grid.add_row("Check Deps", ": None")
        # TODO: Fix hardcoded 'None'
        if "Conflicts" in self.info_query.keys():
            grid.add_row(
                "Optional Deps",
                f": {'  '.join([pkg for pkg in self.info_query['Conflicts']])}",
            )
        else:
            grid.add_row("Conflicts With", ": None")
        if "Maintainer" in self.info_query.keys():
            grid.add_row("Maintainer", f": {self.info_query['Maintainer']}")
        else:
            grid.add_row("Maintainer", ": None")
        grid.add_row("Votes", f": {self.info_query['NumVotes']}")
        grid.add_row("Popularity", f": {self.info_query['Popularity']}")
        grid.add_row(
            "First Submitted",
            f": {datetime.fromtimestamp(self.info_query['FirstSubmitted']).strftime('%d %b %Y %I:%M:%S %p %Z')}",
        )
        grid.add_row(
            "Last Modified",
            f": {datetime.fromtimestamp(self.info_query['LastModified']).strftime('%d %b %Y %I:%M:%S %p %Z')}",
        )
        grid.add_row()

        return grid
