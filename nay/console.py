from rich.theme import Theme
from rich.console import Console

default = Theme(
    {
        "aur": "bright_blue",
        "community": "bright_magenta",
        "extra": "bright_green",
        "core": "bright_yellow",
        "multilib": "bright_cyan",
    }
)

console = Console(theme=default)
