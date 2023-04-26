import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import networkx as nx
import pyalpm
import requests
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Column, Table
from rich.text import Text

from .config import CACHEDIR
from .console import default
from .db import INSTALLED


@dataclass
class Package:
    db: str
    name: str
    version: str
    desc: str

    @property
    def is_installed(self) -> bool:
        return True if self.name in INSTALLED else False

    def __lt__(self, other):
        if isinstance(other, Package):
            if self.db < other.db:
                return True
            elif self.db == other.db:
                if self.name < other.name:
                    return True

    def __hash__(self):
        return hash((self.name, self.version))

    def __eq__(self, other):
        if not isinstance(other, Package):
            return False

        else:
            return hash(self) == hash(other)


@dataclass(eq=False)
class SyncPackage(Package):
    size: int
    isize: int

    def __post_init__(self):
        self.size = self.format_bytes(self.size)
        self.isize = self.format_bytes(self.isize)

    @classmethod
    def from_pyalpm(cls, pkg: pyalpm.Package):
        kwargs = {
            "name": pkg.name,
            "version": pkg.version,
            "desc": pkg.desc,
            "db": pkg.db.name,
            "size": pkg.size,
            "isize": pkg.isize,
        }
        return cls(**kwargs)

    @staticmethod
    def format_bytes(size):
        # TODO: Fix calculations for Kebi/Mebi vs KB/MB. These are not the same.
        power = 2**10
        n = 0
        power_labels = {0: "B", 1: "KiB", 2: "MiB", 3: "GiB", 4: "TiB"}
        while size > power:
            size /= power
            n += 1
        return f"{round(size, 1)} {power_labels[n]}"

    @property
    def renderable(self) -> Text:
        renderable = Text.assemble(
            (
                Text(
                    self.db,
                    style=self.db if self.db in default.styles.keys() else "other_db",
                )
            ),
            (Text("/")),
            (Text(f"{self.name} ")),
            (Text(f"{self.version} ", style="cyan")),
            (Text(f"({self.size} {self.isize}) ")),
            (Text(f"(Installed)" if self.is_installed else "", style="bright_green")),
        )
        renderable = Text("\n    ").join([renderable, Text(self.desc)])
        return renderable

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        yield self.renderable


@dataclass(eq=False)
class AURPackage(Package):
    votes: int
    popularity: float
    flag_date: Optional[int] = None
    orphaned: Optional[bool] = False
    make_depends: Optional[list[str]] = None
    check_depends: Optional[list[str]] = None
    depends: Optional[list[str]] = None
    opt_depends: Optional[list[str]] = None
    info_query: Optional[dict] = None

    def __post_init__(self):
        self.flag_date = (
            datetime.fromtimestamp(self.flag_date) if self.flag_date else None
        )

    @classmethod
    def from_search_query(cls, result: dict):
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

    @classmethod
    def from_info_query(cls, result: dict):
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

        return cls(**kwargs)

    @property
    def PKGBUILD(self):
        return os.path.join(CACHEDIR, f"{self.name}/PKGBUILD")

    @property
    def SRCINFO(self):
        return os.path.join(CACHEDIR, f"{self.name}/.SRCINFO")

    @property
    def pkgbuild_exists(self):
        if os.path.exists(self.PKGBUILD):
            try:
                with open(self.SRCINFO, "r") as f:
                    if re.search(r"pkgver=(.*)", f.read()) != self.version:
                        return True
            except FileNotFoundError:
                return False
        else:
            return False

    @property
    def renderable(self) -> Text:
        flag_date = self.flag_date.strftime("%Y-%m-%d") if self.flag_date else ""
        popularity = "{:.2f}".format(self.popularity)
        renderable = Text.assemble(
            (
                Text(
                    self.db,
                    style=self.db if self.db in default.styles.keys() else "other_db",
                )
            ),
            (Text("/")),
            (Text(f"{self.name} ")),
            (Text(f"{self.version} ", style="cyan")),
            (Text(f"(+{self.votes} {popularity}) ")),
            (Text(f"(Installed) " if self.is_installed else "", style="bright_green")),
            (Text(f"(Orphaned) " if self.orphaned else "", style="bright_red")),
            (
                Text(
                    f"(Out-of-date: {flag_date})" if flag_date else flag_date,
                    style="bright_red",
                )
            ),
        )
        renderable = Text("\n    ").join([renderable, Text(self.desc)])
        return renderable

    def get_aur_dependency_tree(self):
        print(f"Running thread for {self.name}")
        tree = nx.DiGraph()
        tree.add_node(self)
        dtypes = ["check_depends", "make_depends", "depends"]
        all_depends = []
        for dtype in dtypes:
            deps = getattr(self, dtype)
            if isinstance(deps, list):
                all_depends += deps
        if all_depends:
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
    def info(self):
        if not self.info_query:
            query = requests.get(
                f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={self.name}"
            ).json()
            self.info_query = query["results"][0]

        grid = Table.grid(Column("field", width=30), Column("value"))
        grid.add_row("Repository", f": aur")
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
        grid.add_row("Groups", f": None")
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

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        yield self.renderable
