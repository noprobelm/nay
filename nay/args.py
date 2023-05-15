import sys
import os
import argparse
import json
from .exceptions import ConflictingOperations, ConflictingOptions
from . import wrapper


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "%s: %s\n" % (self.prog, message))


parent = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(parent, "args.json"), "r") as f:
    ARGS_MAPPER = json.load(f)


OPERATION_MAPPER = {
    "remove": wrapper.Remove,
    "upgrade": wrapper.Upgrade,
    "query": wrapper.Query,
    "database": wrapper.Database,
    "files": wrapper.Files,
    "deptest": wrapper.Deptest,
    "version": "",
}


def get_operation():
    valid_operations = []
    for arg in ARGS_MAPPER["operations"]:
        valid_operations.extend(ARGS_MAPPER["operations"][arg]["args"])

    selected_operations = []
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            if arg in valid_operations:
                selected_operations.append(arg)
        elif arg.startswith("-"):
            for switch in arg[1:]:
                if f"-{switch}" in valid_operations:
                    selected_operations.append(f"-{switch}")
    if len(selected_operations) == 0:
        selected_operations.append("--nay")
    elif len(selected_operations) > 1:
        raise ConflictingOperations("error: only one operation may be used at a time")

    operation_parser = ArgumentParser(
        description="Argument parser for high level operations"
    )

    for operation in ARGS_MAPPER["operations"]:
        operation_parser.add_argument(
            *ARGS_MAPPER["operations"][operation]["args"],
            **ARGS_MAPPER["operations"][operation]["kwargs"],
        )

    operations = vars(operation_parser.parse_args(selected_operations))
    operation = [operation for operation in operations if operations[operation] is True]

    return operation[0]


def parse_args():
    operation = get_operation()
    pacman_params = []
    unparsed = ARGS_MAPPER[operation]
    unparsed.update(ARGS_MAPPER["global"])
    if operation == "nay":
        unparsed.update(ARGS_MAPPER["sync"])
    if operation in ["sync", "remove", "upgrade", "nay"]:
        unparsed.update(ARGS_MAPPER["transaction"])

    parser = ArgumentParser()

    for arg in unparsed:
        parser.add_argument(
            *unparsed[arg]["args"],
            **unparsed[arg]["kwargs"],
        )
    parsed = parser.parse_args()
    parsed = vars(parsed)
    if operation == "nay":
        del parsed["sync"]
        del parsed["nay"]
        pacman_params.append("--sync")
    else:
        pacman_params.append(f"--{operation}")
        del parsed[operation]

    for arg in parsed:
        if parsed[arg]:
            for other in parsed:
                if parsed[other]:
                    if other in unparsed[arg]["conflicts"]:
                        raise ConflictingOptions(
                            f"error: invalid option: '{arg}' and '{other}' may not be used together"
                        )

            if arg == "targets":
                pass
            elif isinstance(parsed[arg], str):
                pacman_params.append(f"{unparsed[arg]['pacman_param']} {parsed[arg]}")
            elif isinstance(parsed[arg], list):
                pacman_params.append(
                    f"{unparsed[arg]['pacman_param']} {' '.join(parsed[arg])}"
                )
            else:
                for _ in range(parsed[arg]):
                    pacman_params.append(f"{unparsed[arg]['pacman_param']}")

    if operation in ["nay", "sync", "getpkgbuild", "version"]:
        if operation == "nay":
            from . import sync

            cls = sync.Nay
        elif operation == "sync":
            from . import sync

            cls = sync.Sync
        elif operation == "getpkgbuild":
            from . import get_pkgbuild

            cls = get_pkgbuild.GetPKGBUILD

        parsed["pacman_params"] = pacman_params
    else:
        cls = OPERATION_MAPPER[operation]
        parsed = {"targets": parsed["targets"], "pacman_params": pacman_params}

    return {"operation": cls, "args": parsed}
