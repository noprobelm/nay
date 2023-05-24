import os
from typing import Union

__version__ = "0.3.1"

PACKAGE_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_console(color_system: Union[str, None]) -> "NayConsole":
    from .console import NayConsole, THEME_DEFAULT

    return NayConsole(color_system=color_system, theme=THEME_DEFAULT)
