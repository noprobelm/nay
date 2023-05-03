import sys

from . import operations
from .exceptions import ConflictingOperations, InvalidOperation


class Args(dict):
    """
    Class to parse sys.argv arguments

    :cvar OPERATIONS: A dict mapper of valid operations to their respective operations.Operation subclass and acceptable options
    """

    OPERATIONS = {
        "--nay": operations.Nay,
        "-N": operations.Nay,
        "--getpkgbuild": operations.GetPKGBUILD,
        "-G": operations.GetPKGBUILD,
        "--sync": operations.Sync,
        "-S": operations.Sync,
        "--upgrade": operations.Upgrade,
        "-U": operations.Upgrade,
        "--query": operations.Query,
        "-Q": operations.Query,
        "--remove": operations.Remove,
        "-R": operations.Remove,
    }

    def __init__(self) -> None:
        operation = []
        options = []
        targets = []

        if len(sys.argv) == 1:
            super().__init__(
                {"operation": operations.Nay, "options": options, "targets": targets}
            )
            return

        for arg in sys.argv[1:]:
            if arg.startswith("--"):
                if arg in self.OPERATIONS.keys():
                    operation.append(arg)
                else:
                    options.append(arg)
            elif arg.startswith("-"):
                for switch in arg[1:]:
                    if switch.islower():
                        options.append(f"-{switch}")
                    elif switch.isupper():
                        if f"-{switch}" not in self.OPERATIONS.keys():
                            raise InvalidOperation(f"nay: invalid option -- '{switch}'")
                        else:
                            operation.append(f"-{switch}")

            else:
                targets.append(arg)

        if len(operation) > 1:
            raise ConflictingOperations(
                "error: only one operation may be used at a time"
            )

        if len(operation) == 1:
            operation = operation[0]

        else:
            operation = "--nay"

        super().__init__(
            {
                "operation": self.OPERATIONS[operation],
                "options": options,
                "targets": targets,
            }
        )
