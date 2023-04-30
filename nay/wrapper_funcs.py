import subprocess
import shlex
from typing import Optional


def refresh(force: Optional[bool] = False) -> None:
    """
    Refresh the sync database. This is a pure pacman wrapper

    :param force: Flag to force a refresh of the sync database (not recommended)
    :type force: bool
    """
    if force is True:
        subprocess.run(shlex.split("sudo pacman -Syy"))
    else:
        subprocess.run(shlex.split("sudo pacman -Sy"))


def upgrade() -> None:
    """Upgrade all system packages"""
    subprocess.run(shlex.split("sudo pacman -Su"))
