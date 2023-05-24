import argparse
import json
import os
import sys

from . import get_console, ROOT_DIR, wrapper


class ArgumentParser(argparse.ArgumentParser):
    with open(os.path.join(ROOT_DIR, "args.json"), "r") as f:
        ARGS_MAPPER = json.load(f)

    _known_args = {}

    @property
    def known_args(self):
        return self._known_args

    @known_args.setter
    def known_args(self, operation: str) -> None:
        known_args = self.ARGS_MAPPER[operation]
        for parent in self.ARGS_MAPPER["operations"][operation]["parents"]:
            known_args.update(self.ARGS_MAPPER[parent])

        self._known_args = known_args

    def error(self, message):
        self.exit(2, "%s: %s\n" % (self.prog, message))

    def _get_pacman_params(self, args):
        params = []
        known_args = self.known_args

        for arg in args:
            if arg == "targets":
                continue

            if isinstance(args[arg], str):
                params.append(f"{known_args[arg]['pacman_param']} {args[arg]}")
            elif isinstance(args[arg], list):
                print(True)
                params.append(
                    f"{known_args[arg]['pacman_param']} {' '.join(args[arg])}"
                )
            elif args[arg]:
                for _ in range(args[arg]):
                    params.append(f"{known_args[arg]['pacman_param']}")

        return params

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
        parser = argparse.ArgumentParser()
        exclusive = parser.add_mutually_exclusive_group()
        for operation in self.ARGS_MAPPER["operations"]:
            oplist.extend(self.ARGS_MAPPER["operations"][operation]["args"])
            exclusive.add_argument(
                *self.ARGS_MAPPER["operations"][operation]["args"],
                **self.ARGS_MAPPER["operations"][operation]["kwargs"],
            )

        args = self._isolate_operation_args(oplist)
        operations = vars(parser.parse_args(args))
        operation = [
            operation for operation in operations if operations[operation] is True
        ][0]

        self.known_args = operation

        return operation

    def _parse_options(self) -> dict:
        for arg in self.known_args:
            self.add_argument(
                *self.known_args[arg]["args"], **self.known_args[arg]["kwargs"]
            )

        parsed = vars(self.parse_args())
        self._check_conflicts(parsed)

        return parsed

    def _check_conflicts(self, parsed: dict):
        known_args = self.known_args
        for arg in parsed:
            if parsed[arg]:
                for other in parsed:
                    if parsed[other] and other in known_args[arg]["conflicts"]:
                        self.error(
                            f"invalid option: '{arg}' and '{other}' may not be used together"
                        )

    def parse_nay_args(self):
        operation = self._parse_operation()
        args = self._parse_options()
        pacman_params = self._get_pacman_params(args)
        args.update({"pacman_params": pacman_params})

        return {"operation": operation, "args": args}


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
        args = parser.parse_nay_args()

        self.args = args["args"]
        operation_key = args["operation"]

        self._mapper = OperationMapper(operation_key)

        cls = self._mapper[operation_key]
        kwargs = self._get_kwargs()

        super().__init__({"op_cls": cls, "kwargs": kwargs})

    def _get_kwargs(self):
        kwargs = {
            "targets": self.args["targets"],
            "pacman_params": self.args["pacman_params"],
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

    def _get_console(self):
        color_system = "auto"

        if self.args["color"] == "never":
            color_system = None

        console = get_console(color_system)
        return console
