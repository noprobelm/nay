import os
from .package import Package, AURBasic
from .config import CACHEDIR
from typing import Optional
import subprocess
import shlex


def get_pkgbuild(pkg: Package, clonedir: Optional[str] = CACHEDIR) -> None:
    """
    Get the PKGBUILD file from package.Package data

    :param pkg: The package.Package object to get the PKGBUILD for
    :type pkg: package.Package
    :param pkgdir: Optional directory to clone the PKGBUILD to. Default is 'None'
    :type pkgdir: Optional[str]

    """

    if not clonedir:
        clonedir = os.getcwd()
    subprocess.run(
        shlex.split(
            f"git clone https://aur.archlinux.org/{pkg.name}.git {os.path.join(clonedir, pkg.name)}"
        ),
        capture_output=True,
    )


def download(*packages):
    sync = []
    for pkg in packages:
        if isinstance(pkg, AURBasic):
            get_pkgbuild(pkg, CACHEDIR)
        else:
            sync.append(pkg)

    subprocess.run(
        shlex.split(f"sudo pacman -Sw {' '.join([pkg.name for pkg in sync])}")
    )
