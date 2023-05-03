from .console import console
import os
import shutil
from .package import Package
from .config import CACHEDIR
from typing import Optional
import subprocess
import shlex


def clean_cachedir() -> None:
    response = console.input(
        "\n[bright_blue]::[/bright_blue] Do you want to remove all other AUR packages from cache? [Y/n] "
    )

    if response.lower() == "y":
        console.print("removing AUR packages from cache...")
    else:
        return

    os.chdir(CACHEDIR)
    for obj in os.listdir():
        shutil.rmtree(obj, ignore_errors=True)


def clean_untracked() -> None:
    response = console.input(
        "\n[bright_blue]::[/bright_blue] Do you want to remove ALL untracked AUR files? [Y/n] "
    )

    if response.lower() == "y":
        console.print("removing untracked AUR files from cache...")
    else:
        return

    os.chdir(CACHEDIR)
    for obj in os.listdir():
        if os.path.isdir(os.path.join(os.getcwd(), obj)):
            os.chdir(os.path.join(os.getcwd(), obj))
            for _ in os.listdir():
                if _.endswith(".tar.zst"):
                    os.remove(_)
            os.chdir("../")
