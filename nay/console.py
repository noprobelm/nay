import re
import sys
from typing import Optional, Union

from rich.console import Console, Group
from rich.text import Text
from rich.theme import Theme

from .package import AURBasic, AURPackage, SyncPackage

DEFAULT = Theme(
    {
        "aur": "bright_blue",
        "community": "bright_magenta",
        "extra": "bright_green",
        "core": "bright_yellow",
        "multilib": "bright_cyan",
        "other_db": "bright_yellow",
        "prompt": "bright_green",
        "notify": "bright_cyan",
        "alert": "yellow",
        "warn": "red",
        "pkg": "cyan",
        "orphan": "bright_red",
        "installed_status": "bright_green",
    },
    inherit=False,
)


class NayConsole(Console):
    def notify(self, message: str):
        self.print(f"[notify]::[/notify] {message}")

    def alert(self, message: str):
        self.print(f"[alert]->[/alert] {message}")

    def warn(self, message: str, exit=False):
        self.print(f"[warn]->[/warn] {message}")
        if exit is True:
            sys.exit()

    def prompt(self, message: str, affirm: str):
        if (
            affirm
            in self.input(
                f"[prompt]==>[/prompt] {message}\n[prompt]==>[/prompt] "
            ).lower()
        ):
            return True
        return False

    def get_nums(self, message: str):
        selections = self.input(
            f"[prompt]==>[/prompt] {message}\n[prompt]==>[/prompt] "
        )
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

        return selections

    def print_packages(
        self,
        packages: dict[int, Union[SyncPackage, AURBasic]],
        local: "pyalpm.Database",
        include_num: Optional[bool] = False,
    ):
        def get_size(pkg):
            return Text(f"{pkg.size}")

        def get_isize(pkg):
            return Text(f"{pkg.isize}")

        def get_votes(pkg):
            return Text(f"{pkg.votes}")

        def get_popularity(pkg):
            return Text("{:.2f}".format(pkg.popularity))

        def get_orphan(pkg):
            return Text("(Orphaned) ", style="orphan") if pkg.orphaned else Text("")

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
                    style=pkg.db if pkg.db in DEFAULT.styles.keys() else "other_db",
                ),
                Text("/"),
                Text(f"{pkg.name} "),
                Text(f"{pkg.version} ", style="pkg"),
            )

            if isinstance(pkg, SyncPackage):
                renderable.append_text(Text(f"({get_size(pkg)} "))
                renderable.append_text(Text(f"{get_isize(pkg)}) "))
                local_pkg = local.get_pkg(pkg.name)
                if local_pkg:
                    renderable.append_text(
                        Text(
                            f"(Installed: {pkg.version}) ",
                            style="installed_status",
                        )
                    )

            elif isinstance(pkg, AURBasic):
                renderable.append_text(
                    Text(f"(+{get_votes(pkg)} {get_popularity(pkg)}) ")
                )
                local_pkg = local.get_pkg(pkg.name)
                if local_pkg:
                    renderable.append_text(
                        Text(
                            f"(Installed: {pkg.version}) ",
                            style="installed_status",
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

        self.print(render_result)

    def print_pkginfo(self, *packages: AURPackage) -> None:
        group = Group(*[pkg.info for pkg in packages])
        self.print(group)
