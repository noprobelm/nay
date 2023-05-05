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
        parser.add_argument("--root", nargs=1, type=pathlib.Path)
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--arch", nargs=1)
        parser.add_argument("--cachedir", nargs=1, type=pathlib.Path)
        parser.add_argument("--color", choices=["always", "auto", "never"])
        parser.add_argument("--config", nargs=1, type=argparse.FileType("r"))
        parser.add_argument("--debug", action="store_true")
        parser.add_argument("--gpgdir", nargs=1, type=pathlib.Path)
        parser.add_argument("--hookdir", nargs=1, type=pathlib.Path)
        parser.add_argument("--logfile", nargs=1, type=argparse.FileType("w"))
        parser.add_argument("--noconfirm", action="store_true")
        parser.add_argument("--disable-download-timeout", action="store_true")
        parser.add_argument("--sysroot", nargs=1, type=pathlib.Path)

        transact = parser.add_argument_group("Transaction options")
        transact.add_argument("-d", "--nodeps", action="count", default=0)
        transact.add_argument("--assume-installed", nargs=1)
        transact.add_argument("--dbonly", action="store_true")
        transact.add_argument("--noprogressbar", action="store_true")
        transact.add_argument("--noscriptlet", action="store_true")
        transact.add_argument("-p", "--print", action="store_true")
        transact.add_argument("--print-format", nargs=1, action="store_true")

        upgrade = parser.add_argument_group("Upgrade options")
        upgrade.add_argument("-w", "--downloadonly", action="store_true")
        # TODO: Add this flag to install.install() so we can properly
        upgrade.add_argument("--asdeps", action="store_true")
        upgrade.add_argument("--asdeps", action="store_true")

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
