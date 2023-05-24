import os
from . import wrapper
from typing import Union

__version__ = "0.3.1"

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_wrappers_mapper():
    mapper = {
        "remove": wrapper.Remove,
        "upgrade": wrapper.Upgrade,
        "query": wrapper.Query,
        "database": wrapper.Database,
        "files": wrapper.Files,
        "deptest": wrapper.Deptest,
    }
    return mapper


def get_nay_mapper():
    from . import sync, get_pkgbuild

    mapper = {
        "sync": sync.Sync,
        "nay": sync.Nay,
        "getpkgbuild": get_pkgbuild.GetPKGBUILD,
    }

    return mapper


def get_console(color_system: Union[str, None]) -> "NayConsole":
    from .console import NayConsole, THEME_DEFAULT

    return NayConsole(color_system=color_system, theme=THEME_DEFAULT)
