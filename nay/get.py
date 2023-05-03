from .package import Package
from typing import Optional
from .config import CACHEDIR
import os
import shutil
import shlex
import subprocess


def get_pkgbuild(pkg: Package, clonedir: Optional[str] = CACHEDIR, force=False) -> None:
    """
    Get the PKGBUILD file from package.Package data

    :param pkg: The package.Package object to get the PKGBUILD for
    :type pkg: package.Package
    :param pkgdir: Optional directory to clone the PKGBUILD to. Default is 'None'
    :type pkgdir: Optional[str]

    """

    if not clonedir:
        clonedir = os.path.join(os.getcwd(), pkg.name)
    else:
        clonedir = os.path.join(clonedir, pkg.name)
    if force:
        shutil.rmtree(clonedir, ignore_errors=True)

    subprocess.run(
        shlex.split(f"git clone https://aur.archlinux.org/{pkg.name}.git {clonedir}"),
        capture_output=True,
    )
