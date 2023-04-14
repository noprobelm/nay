import sys
from . import operations


class ArgumentError(Exception):
    """Base class for exceptions in this module"""

    pass


class ConflictingOperations(ArgumentError):
    """Conflicting operations were passed as command line arguments"""

    pass


class ConflictingOptions(ArgumentError):
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
            "pure_wrapper": False,
        },
        "G": {
            "operation": operations.GetPKGBUILD,
            "options": {},
            "pure_wrapper": False,
        },
        "N": {"operation": operations.Nay, "options": {}, "pure_wrapper": False},
        "R": {"operation": operations.Remove, "options": {}, "pure_wrapper": True},
        "Q": {"operatoin": operations.Query, "options": {}, "pure_wrapper": True},
    }

    def __init__(self):
        if len(sys.argv) == 1:
            args = []
            operation = "N"
            options = []
        elif sys.argv[1].startswith("-"):
            args = sys.argv[2:]
            operation = [opt for opt in sys.argv[1] if opt.isupper()]
            options = [opt for opt in sys.argv[1] if opt.islower()]
        else:
            args = sys.argv[1:]
            operation = ""
            options = []

        try:

            if len(operation) > 1:
                raise ConflictingOperations(
                    "error: only one operation may be used at a time"
                )
            elif len(operation) == 1:
                operation = operation[0]
            else:
                operation = ""

            if operation not in self.OPERATIONS.keys():
                raise InvalidOperation(f"nay: invalid option -- {operation}")

            if self.OPERATIONS[operation]["pure_wrapper"] == False:
                for opt in options:
                    if opt not in self.OPERATIONS[operation]["options"].keys():
                        raise InvalidOption(f"nay: invalid option '-{opt}'")
                    elif any(
                        _ in options
                        for _ in self.OPERATIONS[operation]["options"][opt]["conflicts"]
                    ):
                        raise ConflictingOptions(f"error: conflicting options")

        except ArgumentError as err:
            print(err)
            quit()

        super().__init__(
            {
                "operation": self.OPERATIONS[operation]["operation"],
                "options": options,
                "args": args,
            }
        )
