from .operations import Operation
from dataclasses import dataclass


@dataclass
class Query(Operation):
    changelog: bool
    deps: bool
    explicit: bool
    group: bool
    info: bool
    check: bool
    _list: bool
    foreign: bool
    native: bool
    owns: bool
    _file: bool
    quiet: bool
    search: bool
    unrequired: bool

    def run(self) -> None:
        self.wrap_pacman(sudo=False)
