import os
import shutil
import subprocess
import shlex
from .config import CACHEDIR
from .console import console


def clean() -> None:
    """Clean up unused package cache data"""

    def clean_pacman() -> None:
        subprocess.run(shlex.split("sudo pacman -Sc"))

    def clean_cachedir() -> None:
        os.chdir(CACHEDIR)
        for obj in os.listdir():
            shutil.rmtree(obj, ignore_errors=True)

    def clean_untracked() -> None:
        os.chdir(CACHEDIR)
        for obj in os.listdir():
            if os.path.isdir(os.path.join(os.getcwd(), obj)):
                os.chdir(os.path.join(os.getcwd(), obj))
                for _ in os.listdir():
                    if _.endswith(".tar.zst"):
                        os.remove(_)
                os.chdir("../")

    clean_pacman()

    response = console.input(
        "\n[bright_blue]::[/bright_blue] Do you want to remove all other AUR packages from cache? [Y/n] "
    )

    if response.lower() == "y":
        console.print("removing AUR packages from cache...")
        clean_cachedir()

    response = console.input(
        "\n[bright_blue]::[/bright_blue] Do you want to remove ALL untracked AUR files? [Y/n] "
    )

    if response.lower() == "y":
        console.print("removing untracked AUR files from cache...")
        clean_untracked()
