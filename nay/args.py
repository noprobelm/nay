import sys

from . import operations


class ArgumentError(Exception):
    """Base class for exceptions in this module"""

    pass


class MissingOperation(ArgumentError):
    """
    Exception raised when options are passed with no operation

    :param message: Explanation of the error
    :type message: str
    """

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
                    options.append(f"-{switch}")
                    if switch.islower():
                        options.append(f"-{switch}")
                    elif switch.isupper():
                        if f"-{switch}" in self.OPERATIONS:
                            operation.append(f"-{switch}")
                        else:
                            options.append(f"-{switch}")

            else:
                targets.append(arg)

        if len(operation) > 1:
            try:
                raise ConflictingOperations(
                    f"error: only one operation may be used at a time"
                )
            except ConflictingOperations as err:
                print(err)

        if len(operation) == 0:
            try:
                raise MissingOperation(f"error: no operation specified")
            except MissingOperation as err:
                print(err)

        operation = operation[0]

        super().__init__(
            {
                "operation": self.OPERATIONS[operation],
                "options": options,
                "targets": targets,
            }
        )
