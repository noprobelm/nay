import pathlib
import argparse

from . import operations
from .exceptions import ConflictingOperations, InvalidOperation


class Args(dict):
    """
    Class to parse sys.argv arguments

    :cvar OPERATIONS: A dict mapper of valid operations to their respective operations.Operation subclass
    """

    OPERATIONS = {
        "nay": operations.Nay,
        "N": operations.Nay,
        "getpkgbuild": operations.GetPKGBUILD,
        "G": operations.GetPKGBUILD,
        "sync": operations.Sync,
        "S": operations.Sync,
        "upgrade": operations.Upgrade,
        "U": operations.Upgrade,
        "database": operations.Database,
        "D": operations.Database,
        "query": operations.Query,
        "Q": operations.Query,
        "remove": operations.Remove,
        "R": operations.Remove,
        "deptest": operations.DepTest,
        "T": operations.DepTest,
        "files": operations.Files,
        "F": operations.Files,
        "version": operations.Version,
        "V": operations.Version,
        "help": operations.Help,
        "h": operations.Help,
    }

    def __init__(self) -> None:
        parser = argparse.ArgumentParser(
            description="Argument parser for high level operations"
        )

        # Add arguments for the operations
        parser.add_argument("-S", "--sync", action="store_true", help="Synchronize")
        parser.add_argument(
            "-D", "--database", action="store_true", help="Database operation"
        )
        parser.add_argument(
            "-N", "--nay", action="store_true", help="Nay-specific operations"
        )
        parser.add_argument("-R", "--remove", action="store_true", help="Remove")
        parser.add_argument("-Q", "--query", action="store_true", help="Query")
        parser.add_argument("-F", "--files", action="store_true", help="Query")
        parser.add_argument("-T", "--deptest", action="store_true", help="Deptest")
        parser.add_argument("-U", "--upgrade", action="store_true", help="Upgrade")
        parser.add_argument("-V", "--version", action="store_true", help="Version")

        parser.add_argument("--dbpath", nargs=1, type=pathlib.Path)
        parser.add_argument("--root", nargs=1)
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--arch", nargs=1)
        parser.add_argument("--cachedir", nargs=1)
        parser.add_argument("--color", choices=["always", "auto", "never"])

        args = parser.parse_args()
        operations = [arg for arg in args.__dict__ if args.__dict__[arg] is True]
        if len(operations) == 0:
            operation = "nay"
        elif len(operations) > 1:
            raise ConflictingOperations(
                "error: only one operation may be used at a time"
            )
        else:
            operation = operations[0]

        super().__init__(
            {
                "operation": self.OPERATIONS[operation],
                "options": options,
                "targets": targets,
            }
        )
