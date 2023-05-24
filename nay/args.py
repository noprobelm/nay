import argparse
import json
import os
import sys

from . import get_operation_mapper, get_console, ROOT_DIR, wrapper


class ArgumentParser(argparse.ArgumentParser):
    with open(os.path.join(ROOT_DIR, "args.json"), "r") as f:
        ARGS_MAPPER = json.load(f)

    _known_args = {}

    @property
    def operation(self):
        return self._operation

    @operation.setter
    def operation(self, operation) -> None:
        self.known_args = operation
        self._operation = operation

    @property
    def known_args(self):
        return self._known_args

    @known_args.setter
    def known_args(self, operation) -> None:
        known_args = self.ARGS_MAPPER[operation]
        for parent in self.ARGS_MAPPER["operations"][operation]["parents"]:
            known_args.update(self.ARGS_MAPPER[parent])

        self._known_args = known_args

    @property
    def nay_args(self) -> dict:
        self._parse_operation()
        args = self._parse_options
        return args

    def error(self, message):
        self.exit(2, "%s: %s\n" % (self.prog, message))

    def _isolate_operation_args(self, oplist: list):
        args = []
        for arg in sys.argv[1:]:
            if arg.startswith("--"):
                if arg in oplist:
                    args.append(arg)
            elif arg.startswith("-"):
                for switch in arg[1:]:
                    if f"-{switch}" in oplist:
                        args.append(f"-{switch}")
        if len(args) == 0:
            args.append("--nay")

        return args

    def _parse_operation(self):
        oplist = []
        exclusive = self.add_mutually_exclusive_group()
        for operation in self.ARGS_MAPPER["operations"]:
            oplist.extend(self.ARGS_MAPPER["operations"][operation]["args"])
            exclusive.add_argument(
                *self.ARGS_MAPPER["operations"][operation]["args"],
                **self.ARGS_MAPPER["operations"][operation]["kwargs"],
            )

        args = self._isolate_operation_args(oplist)
        operations = vars(self.parse_args(args))
        operation = [
            operation for operation in operations if operations[operation] is True
        ][0]

        self.operation = operation

    def _check_conflicts(self, parsed: dict):
        known_args = self.known_args
        for arg in parsed:
            for other in parsed:
                if parsed[other]:
                    if other in known_args[arg]["conflicts"]:
                        self.error(
                            f"invalid option: '{arg}' and '{other}' may not be used together"
                        )

    def _parse_options(self) -> dict:
        for arg in self.known_args:
            self.add_argument(
                *self.known_args[arg]["args"], **self.known_args[arg]["kwargs"]
            )

        parsed = vars(self.parse_args())
        self._check_conflicts(parsed)

        return parsed


class OperationMapper(dict):
    def __init__(self, key):
        self.pure_wrapper = True
        mapper = {
            "remove": wrapper.Remove,
            "upgrade": wrapper.Upgrade,
            "query": wrapper.Query,
            "database": wrapper.Database,
            "files": wrapper.Files,
            "deptest": wrapper.Deptest,
        }

        if key not in mapper:
            from . import sync, get_pkgbuild

            mapper = {
                "sync": sync.Sync,
                "nay": sync.Nay,
                "getpkgbuild": get_pkgbuild.GetPKGBUILD,
            }

            self.pure_wrapper = False

        super().__init__(mapper)


class OperationParams(dict):
    def __init__(self):
        parser = ArgumentParser()
        self.args = parser.nay_args

        operation_key = self.args["operation"]
        self._mapper = OperationMapper(operation_key)

        cls = self._mapper[operation_key]
        kwargs = self._get_kwargs(operation_key)

        super().__init__({"op_cls": cls, "kwargs": kwargs})

    def _get_kwargs(self, operation_key):
        kwargs = {
            "targets": self.args["targets"],
            "pacman_params": self._get_pacman_params(),
        }
        if self._mapper.pure_wrapper is False:
            kwargs.update(
                {
                    "console": self._get_console(),
                    "dbpath": self.args["dbpath"],
                    "root": self.args["root"],
                    "config": self.args["config"],
                }
            )

        return kwargs

    def _get_pacman_params(self):
        params = []
        for arg in self.args:
            if arg == "targets":
                continue

            if isinstance(self.args[arg], str):
                params.append(f"{self.args[arg]}")
            elif isinstance(self.args[arg], list):
                params.append(
                    f"{self.args[arg]['pacman_param']} {' '.join(self.args[arg])}"
                )
            else:
                for _ in range(self.args[arg]):
                    params.append(f"{self.args[arg]['pacman_param']}")

        return params

    def _get_console(self):
        color_system = "auto"

        if self.args["color"] == "never":
            color_system = None

        console = get_console(color_system)
        return console


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
        from .console import NayConsole, DEFAULT

        if parsed["color"] == "never":
            console = NayConsole(color_system=None)

        else:
            console = NayConsole(theme=DEFAULT)

        if operation == "version":
            console.print_version()
            sys.exit()

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
        parsed = {
            "targets": parsed["targets"],
            "pacman_params": pacman_params,
            "dbpath": parsed["dbpath"],
            "root": parsed["root"],
            "config": parsed["config"],
            "console": parsed["console"],
        }

    return {"operation": cls, "args": parsed}
