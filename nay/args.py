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
        "--sync": {
            "short": "-S",
            "operation": operations.Sync,
            "options": {
                "--refresh": {"conflicts": [], "short": "-y"},
                "--sysupgrade": {"conflicts": ["--search"], "short": "-u"},
                "--search": {
                    "conflicts": ["--sysupgrade", "--downloadonly"],
                    "short": "-s",
                },
                "--downloadonly": {"conflicts": ["--info", "--search"], "short": "-w"},
                "--info": {"conflicts": ["--downloadonly", "--search"], "short": "-i"},
                "--clean": {"conflicts": [], "short": "-c"},
            },
            "pure_wrapper": False,
        },
        "--getpkgbuild": {
            "short": "-G",
            "operation": operations.GetPKGBUILD,
            "options": {},
            "pure_wrapper": False,
        },
        "--nay": {
            "short": "-N",
            "operation": operations.Nay,
            "options": {},
            "pure_wrapper": False,
        },
        "--remove": {
            "short": "-R",
            "operation": operations.Remove,
            "options": {},
            "pure_wrapper": True,
        },
        "--query": {
            "short": "-Q",
            "operation": operations.Query,
            "options": {},
            "pure_wrapper": True,
        },
        "--upgrade": {
            "short": "-U",
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

        operation = []
        _options = []
        options = []
        args = []
        valid_operations = [op[2:] for op in self.OPERATIONS.keys()]
        for arg in sys.argv[1:]:
            if arg[:2] == "--":
                if arg in self.OPERATIONS.keys():
                    operation.append(arg)
                else:
                    _options.append(arg)
            elif arg[0] == "-":
                for flag in arg[1:]:
                    if flag.isupper():
                        if flag.lower() not in [op[0] for op in valid_operations]:
                            try:
                                raise InvalidOperation(
                                    f"error: invalid option -- {flag}"
                                )
                            except InvalidOperation as err:
                                print(err)
                                quit()
                        else:
                            for op in valid_operations:
                                if flag.lower() == op[0]:
                                    operation.append(f"--{op}")
                    else:
                        _options.append(f"-{flag}")
            else:
                args.append(arg)

        try:
            if len(operation) > 1:
                try:
                    raise ConflictingOperations(
                        "error: only one operation may be used at a time"
                    )
                except ConflictingOperations as err:
                    print(err)
                    quit()
        except ConflictingOperations as err:
            print(err)
            quit()

        operation = operation[0]

        valid_opts = {}
        if self.OPERATIONS[operation]["pure_wrapper"] == False:
            for long_opt in self.OPERATIONS[operation]["options"].keys():
                short_opt = self.OPERATIONS[operation]["options"][long_opt]["short"]
                valid_opts[long_opt] = short_opt
                valid_opts[short_opt] = long_opt

            for opt in _options:
                if opt not in valid_opts.keys():
                    try:
                        raise InvalidOption(f"error: invalid option '{opt}'")
                    except InvalidOption as err:
                        print(err)
                        quit()
                else:
                    if opt[:2] == "--":
                        options.append(opt)
                    else:
                        options.append(valid_opts[opt])

            for opt in options:
                other = list(filter(lambda x: x != opt, options))
                conflicts = self.OPERATIONS[operation]["options"][opt]["conflicts"]
                for _opt in other:
                    if _opt in conflicts:
                        try:
                            raise ConflictingOptions(
                                f"error: invalid option {opt} and {_opt} may not be used together"
                            )
                        except ConflictingOptions as err:
                            print(err)
                            quit()

        else:
            options = _options

        super().__init__(
            {
                "operation": self.OPERATIONS[operation]["operation"],
                "options": options,
                "args": args,
            }
        )
