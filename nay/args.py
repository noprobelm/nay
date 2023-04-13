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
                "c": {"conflicts": []},
            },
        },
        "R": {"operation": operations.Remove, "options": {}},
        "G": {"operation": operations.GetPKGBUILD, "options": {}},
        "N": {"operation": operations.Nay, "options": {}},
        "": {"operation": operations.Nay, "options": {}},
    }

    def __init__(self):
        args = sys.argv[1:]
        operation = [opt for opt in args[0] if opt.isupper()]

        try:
            if len(operation) > 1:
                raise ConflictingOperations(
                    "error: only one operation may be used at a time"
                )
            elif len(operation) == 1:
                operation = operation[0]
            else:
                operation = ""

        except ConflictingOperations as err:
            print(err)
            quit()

        try:
            optlist, args = getopt.gnu_getopt(
                args,
                f"{operation}{''.join([opt for opt in self.OPERATIONS[operation]['options'].keys()])}",
            )

            operation = []
            options = []
            for opt in optlist:
                opt = opt[0][1]
                if opt.isupper():
                    operation.append(opt)
                elif opt.islower():
                    options.append(opt)

            if len(operation) > 1:
                raise ConflictingOperations(
                    "error: only one operation may be used at a time"
                )
            elif len(operation) == 0:
                operation = ""
            else:
                operation = operation[0]
        except KeyError as err:
            print(f"nay: invalid option -- '{operation}'")
            quit()
        except getopt.GetoptError as err:
            print(f"nay: invalid option '-{err.opt}'")
            quit()

        super().__init__(
            {
                "operation": self.OPERATIONS[operation]["operation"],
                "options": options,
                "args": args,
            }
        )
