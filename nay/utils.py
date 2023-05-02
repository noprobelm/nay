import os
import shlex
import shutil
import subprocess
from typing import Optional
from .package import Package, AURBasic, AURPackage, SyncPackage
from .console import console

from .config import CACHEDIR


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


def makepkg(pkg: Package, pkgdir, flags: str) -> None:
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


def install_aur(
    *packages: AURPackage,
    skip_depchecks: Optional[bool] = False,
    download_only: Optional[bool] = False,
):
    targets = []
    for pkg in packages:
        if skip_depchecks is True:
            makepkg(pkg, CACHEDIR, "fscd")
        else:
            makepkg(pkg, CACHEDIR, "fsc")

        pattern = f"{pkg.name}-"
        for obj in os.listdir(os.path.join(CACHEDIR, pkg.name)):
            if pattern in obj and obj.endswith("zst"):
                targets.append(os.path.join(CACHEDIR, pkg.name, obj))

    if download_only is False:
        subprocess.run(shlex.split(f"sudo pacman -U {' '.join(targets)}"))
    else:
        console.print(
            f"-> nothing to install for {' '.join([target for target in targets])}"
        )


def install_sync(*packages: SyncPackage, pacman_flags: list[str]):
    subprocess.run(
        shlex.split(f"sudo pacman -S{' '.join(flag for flag in pacman_flags)}")
    )
