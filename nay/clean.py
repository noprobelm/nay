import os
import shutil
import subprocess
import shlex
from .config import CACHEDIR
from .console import console


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
