import shlex
import subprocess
from dataclasses import dataclass


@dataclass
class Wrapper:
    targets: list[str]
    pacman_params: list[str]

    def wrap_pacman(self, sudo: bool):
        prefix = "sudo " if sudo is True else ""
        params = self.pacman_params + [" ".join(self.targets)]
        subprocess.run(shlex.split(f"{prefix}pacman {' '.join([p for p in params])}"))


@dataclass
class Transaction(Wrapper):
    def run(self) -> None:
        sudo = True
        if "--print" in self.pacman_params:
            sudo = False

        self.wrap_pacman(sudo=sudo)


@dataclass
class Remove(Transaction):
    pass


@dataclass
class Upgrade(Transaction):
    pass


@dataclass
class Query(Wrapper):
    def run(self) -> None:
        self.wrap_pacman(sudo=False)


@dataclass
class Database(Wrapper):
    def run(self) -> None:
        sudo = False
        if self.targets:
            self.sudo = True
        if "--check" in self.pacman_params:
            sudo = False

        self.wrap_pacman(sudo=sudo)


@dataclass
class Files(Wrapper):
    def run(self) -> None:
        sudo = False
        if "--refresh" in self.pacman_params:
            sudo = True
        self.wrap_pacman(sudo=sudo)


@dataclass
class Deptest(Wrapper):
    def run(self):
        self.wrap_pacman(sudo=False)
