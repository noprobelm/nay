import subprocess
import shlex
import os
from .config import CACHEDIR
import shutil
from .package import Package
from typing import Optional


def makepkg(pkg: Package, pkgdir: str, flags: str) -> None:
    """
    Make a package using 'makepkg'. This is a pure pacman wrapper.

    :param pkg: The package.Package object to make the package from
    :type pkg: package.Package
    :param pkgdir: The full path (exclusive of the package path itself)
    :type pkgdir: str
    :param flags: The flags to pass to 'makepkg' (exlusive of the leading '-')
    :type flags: str

    """
    os.chdir(f"{pkgdir}/{pkg.name}")
    return_code = subprocess.run(shlex.split(f"makepkg -{flags}")).returncode
    if return_code != 0:
        console.print(f"[red] -> error making: {pkg.name}-exit status {return_code}")
        console.print(
            f"[red] Failed to install {pkg.name}. Manual intervention is required"
        )
        quit()


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
