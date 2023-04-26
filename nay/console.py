from rich.console import Console
from rich.theme import Theme

default = Theme(
    {
        "aur": "bright_blue",
        "community": "bright_magenta",
        "extra": "bright_green",
        "core": "bright_yellow",
        "multilib": "bright_cyan",
        "other_db": "bright_yellow",
    }
)

console = Console(theme=default)
