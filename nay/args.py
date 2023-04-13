import getopt
import sys
from . import operations
from dataclasses import dataclass
from typing import Optional


class ArgumentError(Exception):
    """Base class for exceptions in this module"""

    pass


class ConflictingOperations(ArgumentError):
    """Conflicting operations were passed as command line arguments"""

    pass


class InvalidOperation(ArgumentError):
    "An invalid operation was passed as a command line argument"

    pass


class InvalidOption(ArgumentError):
    """Invalid options were passed as command line arguments"""

    pass


@dataclass
class Option:
    option: str
    stacks: Optional[int] = 0
    conflicts: Optional[list[str]] = None


class Args(dict):
    OPERATIONS = {
        "S": {
            "operation": operations.Sync,
            "options": {
                "y": {"conflicts": []},
                "u": {"conflicts": ["s"]},
                "s": {"conflicts": ["u", "w"]},
                "w": {"conflicts": ["i", "s"]},
                "i": {"conflicts": ["w", "s"]},
            },
        },
        "Q": {"operation": operations.Query, "options": {}},
        "G": {"operation": operations.GetPKGBUILD, "options": {}},
        "R": {"operation": operations.Remove, "options": {}},
        "P": {"operation": operations.Nay, "options": {}},
        "": {"operation": operations.Nay, "options": {}},
    }

    def __init__(self):
        args = sys.argv[1:]
        operations = [opt for opt in args[0] if opt.isupper()]
        options = [opt for opt in args[0] if opt.islower()]
        if len(operations) > 1:
            try:
                raise ConflictingOperations(
                    "error: only one operation may be used at a time"
                )
            except ConflictingOperations as err:
                print(err)
                quit()
        else:
            operation = operations[0]
        try:
            optlist, args = getopt.gnu_getopt(
                args,
                f"{operation}{''.join([key for key in self.OPERATIONS[operation]['options'].keys()])}",
            )
        except getopt.GetoptError:
            try:
                if operation not in self.OPERATIONS.keys():
                    raise InvalidOperation(f"nay: invalid option -- '{operation}'")
                for opt in options:
                    if (
                        opt not in self.OPERATIONS[operation]["options"].keys()
                        and operation != "S"
                    ):
                        args = sys.argv[2:]
                        super().__init__(
                            {
                                "operation": self.OPERATIONS[operation]["operation"],
                                "options": options,
                                "args": args,
                            }
                        )
                    else:
                        raise InvalidOption(f"nay: invalid option -'{opt}'")
            except ArgumentError as err:
                print(err)
                quit()

        optlist = {"operation": operation, "options": options}
        optlist = self.parse_options(optlist)
        super().__init__(
            {
                "operation": self.OPERATIONS[optlist["operation"]]["operation"],
                "options": optlist["options"],
                "args": args,
            }
        )

    def parse_options(self, optlist):
        optlist["options"] = sorted(optlist["options"])
        return optlist
