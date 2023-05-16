import sys
import os
import argparse
import json
from . import wrapper


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "%s: %s\n" % (self.prog, message))


parent = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(parent, "args.json"), "r") as f:
    ARGS_MAPPER = json.load(f)


WRAPPERS = {
    "remove": wrapper.Remove,
    "upgrade": wrapper.Upgrade,
    "query": wrapper.Query,
    "database": wrapper.Database,
    "files": wrapper.Files,
    "deptest": wrapper.Deptest,
    "version": "",
}


def parse_operation():
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

    parser = ArgumentParser(description="Argument parser for high level operations")

    exclusive = parser.add_mutually_exclusive_group()
    for operation in ARGS_MAPPER["operations"]:
        exclusive.add_argument(
            *ARGS_MAPPER["operations"][operation]["args"],
            **ARGS_MAPPER["operations"][operation]["kwargs"],
        )

    operations = vars(parser.parse_args(selected_operations))
    operation = [operation for operation in operations if operations[operation] is True]

    return operation[0]


def parse_args():
    operation = parse_operation()
    pacman_params = []
    unparsed = ARGS_MAPPER[operation]
    for parent in ARGS_MAPPER["operations"][operation]["parents"]:
        unparsed.update(ARGS_MAPPER[parent])

    parser = ArgumentParser()

    for arg in unparsed:
        parser.add_argument(
            *unparsed[arg]["args"],
            **unparsed[arg]["kwargs"],
        )

    parsed = vars(parser.parse_args())
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
                        parser.error(
                            f"invalid option: '{arg}' and '{other}' may not be used together"
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

    if ARGS_MAPPER["operations"][operation]["pure_wrapper"] is True:
        cls = WRAPPERS[operation]
        parsed = {"targets": parsed["targets"], "pacman_params": pacman_params}

    else:
        from .console import NayConsole

        console = NayConsole()
        if operation in ["sync", "nay"]:
            from . import sync

            if operation == "sync":
                cls = sync.Sync
            elif operation == "nay":
                cls = sync.Nay
        elif operation == "getpkgbuild":
            from . import get_pkgbuild

            cls = get_pkgbuild.GetPKGBUILD

        parsed["console"] = console
        parsed["pacman_params"] = pacman_params

    return {"operation": cls, "args": parsed}
