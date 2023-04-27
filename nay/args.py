import sys

from . import operations


class ArgumentError(Exception):
    """Base class for exceptions in this module"""

    pass


class ConflictingOperations(ArgumentError):
    """
    Exception raised when conflicting operations are passed as command line arguments.

    :param message: Explanation of the error
    :type message: str
    """

    pass


class ConflictingOptions(ArgumentError):
    """
    Exception raised when conflicting options are passed as command line arguments.

    :param message: Explanation of the error
    :type message: str
    """

    pass


class InvalidOperation(ArgumentError):
    """
    Exception raised when an invalid operation is passed as a command line argument.

    :param message: Explanation of the error
    :type message: str
    """

    pass


class InvalidOption(ArgumentError):
    """
    Exception raised when invalid options are passed as command line arguments.

    :param message: Explanation of the error
    :type message: str
    """

    pass


class Args(dict):
    """
    Class to parse sys.argsv arguments

    :cvar OPERATIONS: A dict mapper of valid operations to their respective operations.Operation subclass and acceptable options
    """

    OPERATIONS = {
        "sync": {
            "short": "S",
            "operation": operations.Sync,
            "options": {
                "y": {"conflicts": [], "long": "refresh", "stacks": 2},
                "u": {"conflicts": ["s"], "long": "sysupgrade", "stacks": 1},
                "s": {"conflicts": ["u", "w"], "long": "search", "stacks": 1},
                "w": {"conflicts": ["i", "s"], "long": "downloadonly", "stacks": 1},
                "i": {"conflicts": ["w", "s"], "long": "info", "stacks": 1},
                "c": {"conflicts": [], "long": "clean", "stacks": 1},
            },
            "pure_wrapper": False,
        },
        "getpkgbuild": {
            "short": "G",
            "operation": operations.GetPKGBUILD,
            "options": {},
            "pure_wrapper": False,
        },
        "nay": {
            "short": "N",
            "operation": operations.Nay,
            "options": {},
            "pure_wrapper": False,
        },
        "remove": {
            "short": "R",
            "operation": operations.Remove,
            "options": {},
            "pure_wrapper": True,
        },
        "query": {
            "short": "Q",
            "operation": operations.Query,
            "options": {},
            "pure_wrapper": True,
        },
        "upgrade": {
            "short": "U",
            "operation": operations.Upgrade,
            "options": {},
            "pure_wrapper": True,
        },
    }

    def __init__(self) -> None:
        if len(sys.argv) == 1:
            super().__init__(
                {
                    "operation": self.OPERATIONS["nay"]["operation"],
                    "options": [],
                    "args": [],
                }
            )
            return

        else:
            short_operations = [
                operation[0].upper() for operation in self.OPERATIONS.keys()
            ]
            args = []
            operations = []
            options = []
            for arg in sys.argv[1:]:
                if arg.startswith("--"):
                    arg = arg[2:]
                    if arg in self.OPERATIONS.keys():
                        operations.append(arg)
                    else:
                        options.append(arg)
                elif arg.startswith("-"):
                    arg = arg[1:]
                    for char in arg:
                        if char.isupper():
                            operations.append(char)
                        else:
                            options.append(char)
                else:
                    args.append(arg)

        try:
            if len(operations) > 1:
                raise ConflictingOperations(
                    "error: only one operation may be used at a time"
                )
            elif len(operations) == 0:
                operation = "nay"
            else:
                operation = operations[0]

            if (
                operation not in short_operations
                and operation not in self.OPERATIONS.keys()
            ):

                raise InvalidOperation(f"nay: invalid option -- {operation}")

            for valid in self.OPERATIONS.keys():
                if operation.lower() == valid[0]:
                    operation = valid
                    break

            if self.OPERATIONS[operation]["pure_wrapper"] == False:
                valid_options = {}
                for short_opt in self.OPERATIONS[operation]["options"]:
                    valid_options[short_opt] = self.OPERATIONS[operation]["options"][
                        short_opt
                    ]["long"]
                for num, opt in enumerate(options):
                    if (
                        opt not in valid_options.keys()
                        and opt not in valid_options.values()
                    ):
                        raise InvalidOption(f"nay: invalid option '-{opt}'")
                    else:
                        options.pop(num)
                        if opt in valid_options.keys():
                            options.append(opt)
                        else:
                            _valid_options = {
                                long_opt: short_opt
                                for short_opt, long_opt in valid_options.items()
                            }

                            options.append(_valid_options[opt])

                for opt in options:
                    if any(
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
