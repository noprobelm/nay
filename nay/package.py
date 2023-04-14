from .console import console
from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text
from rich.table import Table, Column
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import pyalpm
import requests
from .db import INSTALLED


@dataclass(eq=False)
class Package:
    db: str
    name: str
    version: str
    desc: str
    url: str

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


@dataclass(eq=False)
class SyncDB(Package):
    size: int
    isize: int

    def __post_init__(self):
        self.size = self.format_bytes(self.size)
        self.isize = self.format_bytes(self.isize)

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
            (Text(self.db, style=self.db)),
            (Text("/")),
            (Text(f"{self.name} ")),
            (Text(f"{self.version} ", style="cyan")),
            (Text(f"({self.size} {self.isize}) ")),
            (Text(f"(Installed)" if self.is_installed else "", style="bright_green")),
        )
        renderable = Text("\n    ").join([renderable, Text(self.desc)])
        return renderable

    @classmethod
    def from_pyalpm(cls, pkg: pyalpm.Package):
        kwargs = {
            "name": pkg.name,
            "version": pkg.version,
            "desc": pkg.desc,
            "db": pkg.db.name,
            "url": pkg.url,
            "size": pkg.size,
            "isize": pkg.isize,
        }
        return cls(**kwargs)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        yield self.renderable


@dataclass(eq=False)
class AUR(Package):
    votes: int
    popularity: float
    flag_date: Optional[int] = None
    orphaned: Optional[bool] = False
    query: Optional[dict] = None

    def __post_init__(self):
        self.flag_date = (
            datetime.fromtimestamp(self.flag_date) if self.flag_date else None
        )

    @property
    def renderable(self) -> Text:
        flag_date = self.flag_date.strftime("%Y-%m-%d") if self.flag_date else ""
        popularity = "{:.2f}".format(self.popularity)
        renderable = Text.assemble(
            (Text(self.db, style=self.db)),
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

    @property
    def info(self):
        if not self.query:
            query = requests.get(
                f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={self.name}"
            ).json()
            self.query = query["results"][0]

        grid = Table.grid(Column("field", width=30), Column("value"))
        grid.add_row("Repository", f": aur")
        grid.add_row("Name", f": {self.query['Name']}")
        grid.add_row(
            "Keywords",
            f": {self.query['Keywords'] if self.query['Keywords'] else None}",
        )
        grid.add_row("Version", f": {self.query['Version']}")
        grid.add_row("Description", f": {self.query['Description']}")
        grid.add_row("URL", f": {self.query['URL']}")
        grid.add_row("AUR URL", f": https://aur.archlinux.org/packages/{self.name}")
        # TODO: Fix hardcoded 'None'
        grid.add_row("Groups", f": None")
        grid.add_row("License", f": {'  '.join([_ for _ in self.query['License']])}")
        grid.add_row(
            "Provides", f": {'  '.join([pkg for pkg in self.query['Provides']])}"
        )
        grid.add_row(
            "Depends On", f": {'  '.join([pkg for pkg in self.query['Depends']])}"
        )
        grid.add_row(
            "Make Deps", f": {'  '.join([pkg for pkg in self.query['MakeDepends']])}"
        )
        # TODO: Fix hardcoded 'None'
        grid.add_row("Check Deps", ": None")
        # TODO: Fix hardcoded 'None'
        grid.add_row("Optional Deps", ": None")
        # TODO: Fix hardcoded 'None'
        grid.add_row("Conflicts With", ": None")
        grid.add_row("Maintainer", f": {self.query['Maintainer']}")
        grid.add_row("Votes", f": {self.query['NumVotes']}")
        grid.add_row("Popularity", f": {self.query['Popularity']}")
        grid.add_row(
            "First Submitted",
            f": {datetime.fromtimestamp(self.query['FirstSubmitted']).strftime('%s %d %b %Y %I:%M:%S %p %Z')}",
        )
        grid.add_row(
            "Last Modified",
            f": {datetime.fromtimestamp(self.query['LastModified']).strftime('%s %d %b %Y %I:%M:%S %p %Z')}",
        )

        return grid

    @classmethod
    def from_query(cls, result: dict):
        kwargs = {
            "db": "aur",
            "name": result["Name"],
            "version": result["Version"],
            "desc": result["Description"],
            "url": result["URL"],
            "votes": result["NumVotes"],
            "popularity": result["Popularity"],
            "query": result,
        }
        return cls(**kwargs)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        yield self.renderable
