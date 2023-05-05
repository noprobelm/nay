import pathlib
import sys
import argparse

from . import operations
from .exceptions import ConflictingOperations, InvalidOperation


COMMON = {
    "dbpath": {"args": ["--dbpath"], "kwargs": {"nargs": 1, "type": pathlib.Path}},
    "root": {"args": ["--root"], "kwargs": {"nargs": 1, "type": pathlib.Path}},
    "verbose": {"args": ["--verbose"], "kwargs": {"action": "store_true"}},
    "arch": {"args": ["--arch"], "kwargs": {"nargs": 1}},
    "cachedir": {
        "args": ["--cachedir"],
        "kwargs": {"nargs": 1, "type": pathlib.Path},
    },
    "color": {
        "args": ["--color"],
        "kwargs": {"choices": ["always", "auto", "never"]},
    },
    "config": {
        "args": ["--config"],
        "kwargs": {"nargs": 1, "type": argparse.FileType("r")},
    },
    "debug": {"args": ["--debug"], "kwargs": {"action": "store_true"}},
    "gpgdir": {"args": ["--gpgdir"], "kwargs": {"nargs": 1, "type": pathlib.Path}},
    "hookdir": {
        "args": ["--hookdir"],
        "kwargs": {"nargs": 1, "type": pathlib.Path},
    },
    "logfile": {
        "args": ["--logfile"],
        "kwargs": {"nargs": 1, "type": argparse.FileType("r")},
    },
    "noconfirm": {"args": ["--noconfirm"], "kwargs": {"action": "store_true"}},
    "disable-download-timeout": {
        "args": ["--disable-download-timeout"],
        "kwargs": {"action": "store_true"},
    },
    "sysroot": {
        "args": ["--sysroot"],
        "kwargs": {"nargs": 1, "type": pathlib.Path},
    },
    "targets": {"args": ["targets"], "kwargs": {"nargs": "*"}},
}


class UpgradeArgs:
    ARGS = {
        "upgrade": {"args": ["-U", "--upgrade"], "kwargs": {"nargs": 1}},
        "nodeps": {
            "args": ["-d", "--nodeps"],
            "kwargs": {"action": "count", "default": 0},
        },
        "assume-installed": {"args": ["--assume-installed"], "kwargs": {"nargs": 1}},
        "dbonly": {"args": ["--dbonly"], "kwargs": {"action": "store_true"}},
        "noprogressbar": {
            "args": ["--noprogressbar"],
            "kwargs": {"action": "store_true"},
        },
        "noscriptlet": {"args": ["--noscriptlet"], "kwargs": {"action": "store_true"}},
        "print": {"args": ["-p, --print"], "kwargs": {"action": "store_true"}},
        "--print-format": {"args": ["--print-format"], "kwargs": {"nargs": 1}},
        "downloadonly": {
            "args": ["-w", "--downloadonly"],
            "kwargs": {"action": "store_true"},
        },
        "asdeps": {"args": ["--aspdeps"], "kwargs": {"action": "store_true"}},
        "asexplicit": {"args": ["--asexplicit"], "kwargs": {"action": "store_true"}},
        "ignore": {"args": ["--ignore"], "kwargs": {"action": "store_true"}},
        "needed": {"args": ["--needed"], "kwargs": {"action": "store_true"}},
        "overwrite": {"args": ["--overwrite"], "kwargs": {"nargs": "+"}},
    }


class RemoveArgs:
    ARGS = {
        "remove": {"args": ["-R", "--remove"], "kwargs": {"action": "store_true"}},
        "nodeps": {
            "args": ["-d", "--nodeps"],
            "kwargs": {"action": "count", "default": 0},
        },
        "assume-installed": {"args": ["--assume-installed"], "kwargs": {"nargs": 1}},
        "dbonly": {"args": ["--dbonly"], "kwargs": {"action": "store_true"}},
        "noprogressbar": {
            "args": ["--noprogressbar"],
            "kwargs": {"action": "store_true"},
        },
        "noscriptlet": {"args": ["--noscriptlet"], "kwargs": {"action": "store_true"}},
        "print": {"args": ["-p, --print"], "kwargs": {"action": "store_true"}},
        "print-format": {"args": ["--print-format"], "kwargs": {"nargs": 1}},
    }


class SyncArgs:
    ARGS = {
        "sync": {"args": ["-S", "--sync"], "kwargs": {"action": "store_true"}},
        "nodeps": {
            "args": ["-d", "--nodeps"],
            "kwargs": {"action": "count", "default": 0},
        },
        "assume-installed": {"args": ["--assume-installed"], "kwargs": {"nargs": 1}},
        "dbonly": {"args": ["--dbonly"], "kwargs": {"action": "store_true"}},
        "noprogressbar": {
            "args": ["--noprogressbar"],
            "kwargs": {"action": "store_true"},
        },
        "noscriptlet": {"args": ["--noscriptlet"], "kwargs": {"action": "store_true"}},
        "print": {"args": ["-p, --print"], "kwargs": {"action": "store_true"}},
        "--print-format": {"args": ["--print-format"], "kwargs": {"nargs": 1}},
        "downloadonly": {
            "args": ["-w", "--downloadonly"],
            "kwargs": {"action": "store_true"},
        },
        "asdeps": {"args": ["--aspdeps"], "kwargs": {"action": "store_true"}},
        "asexplicit": {"args": ["--asexplicit"], "kwargs": {"action": "store_true"}},
        "ignore": {"args": ["--ignore"], "kwargs": {"action": "store_true"}},
        "needed": {"args": ["--needed"], "kwargs": {"action": "store_true"}},
        "overwrite": {"args": ["--overwrite"], "kwargs": {"nargs": "+"}},
        "clean": {
            "args": ["-c", "--clean"],
            "kwargs": {"action": "count", "default": 0},
        },
        "groups": {"args": ["-g", "--groups"], "kwargs": {"action": "store_true"}},
        "info": {"args": ["-i", "--info"], "kwargs": {"action": "store_true"}},
        "list": {"args": ["-l", "--list"], "kwargs": {"action": "store_true"}},
        "quiet": {"args": ["-q", "--quiet"], "kwargs": {"action": "store_true"}},
        "search": {"args": ["-s", "--search"], "kwargs": {"action": "store_true"}},
        "sysupgrade": {
            "args": ["-u", "--sysupgrade"],
            "kwargs": {"action": "store_true"},
        },
        "refresh": {"args": ["-y", "--refresh"], "kwargs": {"action": "store_true"}},
    }
    ARGS.update(COMMON)


class DatabaseArgs:
    ARGS = {
        "database": {"args": ["-D", "--database"], "kwargs": {"action": "store_true"}},
        "asdeps": {"args": ["--asdeps"], "kwargs": {"action": "store_true"}},
        "asexplicit": {
            "args": ["--asexplicit"],
            "kwargs": {"action": "store_true"},
        },
        "check": {"args": ["-k", "--check"], "kwargs": {"action": "store_true"}},
        "quiet": {"args": ["-q", "--quiet"], "kwargs": {"action": "store_true"}},
    }


class QueryArgs:
    ARGS = {
        "query": {"args": ["-Q", "--query"], "kwargs": {"action": "store_true"}},
        "changelog": {
            "args": ["-c", "--changelog"],
            "kwargs": {"action": "store_true"},
        },
        "deps": {"args": ["-d", "--deps"], "kwargs": {"action": "store_true"}},
        "explicit": {"args": ["-e", "--explicit"], "kwargs": {"action": "store_true"}},
        "group": {"args": ["-g", "--group"], "kwargs": {"action": "store_true"}},
        "info": {"args": ["-i", "--info"], "kwargs": {"action": "store_true"}},
        "check": {"args": ["-k", "--check"], "kwargs": {"action": "store_true"}},
        "list": {"args": ["-l", "--list"], "kwargs": {"action": "store_true"}},
        "foreign": {"args": ["-m", "--foreign"], "kwargs": {"action": "store_true"}},
        "native": {"args": ["-n", "--native"], "kwargs": {"action": "store_true"}},
        "owns": {"args": ["-o", "--owns"], "kwargs": {"action": "store_true"}},
        "file": {"args": ["-p", "--file"], "kwargs": {"action": "store_true"}},
        "quiet": {"args": ["-q", "--quiet"], "kwargs": {"action": "store_true"}},
        "search": {"args": ["-s", "--search"], "kwargs": {"action": "store_true"}},
        "unrequired": {
            "args": ["-t", "--unrequired"],
            "kwargs": {"action": "store_true"},
        },
    }


class FilesArgs:
    ARGS = {
        "files": {"args": ["-F", "--files"], "kwargs": {"action": "store_true"}},
        "refresh": {"args": ["-y", "--refresh"], "kwargs": {"action": "store_true"}},
        "list": {"args": ["-l", "--list"], "kwargs": {"action": "store_true"}},
        "regex": {"args": ["-x", "--regex"], "kwargs": {"action": "store_true"}},
        "quiet": {"args": ["-q", "--quiet"], "kwargs": {"action": "store_true"}},
        "machinereadable": {
            "args": ["--machinereadable"],
            "kwargs": {"action": "store_true"},
        },
    }


class DeptestArgs:
    ARGS = {
        "deptest": {"args": ["-T", "--deptest"], "kwargs": {"action": "store_true"}}
    }
    ARGS.update(COMMON)


class VersionArgs:
    ARGS = {
        "version": {"args": ["-V", "--version"], "kwargs": {"action": "store_true"}}
    }
    ARGS.update(COMMON)


class NayArgs:
    ARGS = {"nay": {"args": ["-N", "--nay"], "kwargs": {"action": "store_true"}}}
    ARGS.update(COMMON)


class GetPKGBUILIDArgs:
    ARGS = COMMON


class Args:
    __COMMON = {
        "dbpath": {"args": ["--dbpath"], "kwargs": {"nargs": 1, "type": pathlib.Path}},
        "root": {"args": ["--root"], "kwargs": {"nargs": 1, "type": pathlib.Path}},
        "verbose": {"args": ["--verbose"], "kwargs": {"action": "store_true"}},
        "arch": {"args": ["--arch"], "kwargs": {"nargs": 1}},
        "cachedir": {
            "args": ["--cachedir"],
            "kwargs": {"nargs": 1, "type": pathlib.Path},
        },
        "color": {
            "args": ["--color"],
            "kwargs": {"choices": ["always", "auto", "never"]},
        },
        "config": {
            "args": ["--config"],
            "kwargs": {"nargs": 1, "type": argparse.FileType("r")},
        },
        "debug": {"args": ["--debug"], "kwargs": {"action": "store_true"}},
        "gpgdir": {"args": ["--gpgdir"], "kwargs": {"nargs": 1, "type": pathlib.Path}},
        "hookdir": {
            "args": ["--hookdir"],
            "kwargs": {"nargs": 1, "type": pathlib.Path},
        },
        "logfile": {
            "args": ["--logfile"],
            "kwargs": {"nargs": 1, "type": argparse.FileType("r")},
        },
        "noconfirm": {"args": ["--noconfirm"], "kwargs": {"action": "store_true"}},
        "disable-download-timeout": {
            "args": ["--disable-download-timeout"],
            "kwargs": {"action": "store_true"},
        },
        "sysroot": {
            "args": ["--sysroot"],
            "kwargs": {"nargs": 1, "type": pathlib.Path},
        },
        "targets": {"args": ["targets"], "kwargs": {"nargs": "*"}},
    }

    __OPERATIONS = {
        "remove": {"args": ["-R", "--remove"], "kwargs": {"action": "store_true"}},
        "upgrade": {
            "args": ["-U", "--upgrade"],
            "kwargs": {"action": "store_true"},
        },
        "sync": {"args": ["-S", "--sync"], "kwargs": {"action": "store_true"}},
        "query": {"args": ["-Q", "--query"], "kwargs": {"action": "store_true"}},
        "database": {
            "args": ["-D", "--database"],
            "kwargs": {"action": "store_true"},
        },
        "files": {"args": ["-F", "--files"], "kwargs": {"action": "store_true"}},
        "nay": {"args": ["-N", "--nay"], "kwargs": {"action": "store_true"}},
        "getpkgbuild": {
            "args": ["-G", "--getpkgbuild"],
            "kwargs": {"action": "store_true"},
        },
        "deptest": {
            "args": ["-T", "--deptest"],
            "kwargs": {"action": "store_true"},
        },
        "version": {
            "args": ["-V", "--version"],
            "kwargs": {"action": "store_true"},
        },
    }

    __OPERATION_MAPPER = {
        "remove": RemoveArgs,
        "upgrade": UpgradeArgs,
        "sync": SyncArgs,
        "query": QueryArgs,
        "database": DatabaseArgs,
        "files": FilesArgs,
        "nay": NayArgs,
        "getpkgbuild": GetPKGBUILIDArgs,
        "deptest": DeptestArgs,
        "version": VersionArgs,
    }

    def __init__(self) -> None:
        operation = self.operation
        args = self.__OPERATION_MAPPER[operation].ARGS
        args.update(self.__COMMON)
        parser = argparse.ArgumentParser()

        for arg in args:
            parser.add_argument(
                *args[arg]["args"],
                **args[arg]["kwargs"],
            )

        args = parser.parse_args()
        print(args)
        quit()

    @property
    def operation(self):
        valid_operations = []
        for arg in self.__OPERATIONS:
            valid_operations.extend(self.__OPERATIONS[arg]["args"])

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
            raise ConflictingOperations(
                "error: only one operation may be used at a time"
            )

        operation_parser = argparse.ArgumentParser(
            description="Argument parser for high level operations"
        )

        for operation in self.__OPERATIONS:
            operation_parser.add_argument(
                *self.__OPERATIONS[operation]["args"],
                **self.__OPERATIONS[operation]["kwargs"],
            )

        operations = vars(operation_parser.parse_args(selected_operations))
        operation = [
            operation for operation in operations if operations[operation] is True
        ]

        return operation[0]
