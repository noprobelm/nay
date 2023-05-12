from .operations import Operation
from dataclasses import dataclass


@dataclass
class Remove(Operation):
    nodeps: bool
    assume_installed: list[str]
    dbonly: bool
    noprogressbar: bool
    noscriptlet: bool
    print_only: bool
    print_format: str
    cascade: bool
    nosave: bool
    recursive: bool
    unneeded: bool

    def run(self) -> None:
        sudo = True
        if "--print" in self.pacman_params:
            sudo = False

        self.blind_wrap(sudo=sudo)
