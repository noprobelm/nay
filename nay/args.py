import pathlib
import sys
import argparse
import re
from dataclasses import dataclass
from typing import Iterable

from . import operations
from . import sync
from . import remove
from .exceptions import ConflictingOperations, InvalidOperation, ConflictingOptions


UPGRADE_ARGS = {
    "upgrade": {
        "args": ["-U", "--upgrade"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--upgrade",
    },
    "nodeps": {
        "args": ["-d", "--nodeps"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": [],
        "pacman_param": "--nodeps",
    },
    "assume_installed": {
        "args": ["--assume-installed"],
        "kwargs": {"nargs": "+", "dest": "assume_installed"},
        "conflicts": [],
        "pacman_param": "--assume_installed",
    },
    "dbonly": {
        "args": ["--dbonly"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--dbonly",
    },
    "noprogressbar": {
        "args": ["--noprogressbar"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--noprogressbar",
    },
    "noscriptlet": {
        "args": ["--noscriptlet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--noscriptlet",
    },
    "print_only": {
        "args": ["-p", "--print"],
        "kwargs": {"action": "store_true", "dest": "print_only"},
        "conflicts": [],
        "pacman_param": "--print",
    },
    "print_format": {
        "args": ["--print-format"],
        "kwargs": {"nargs": "+"},
        "conflicts": [],
        "pacman_param": "--print-format",
    },
    "download_only": {
        "args": ["-w", "--downloadonly"],
        "kwargs": {"action": "store_true", "dest": "download_only"},
        "conflicts": [],
        "pacman_param": "--downloadonly",
    },
    "asdeps": {
        "args": ["--aspdeps"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--asdeps",
    },
    "asexplicit": {
        "args": ["--asexplicit"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--asexplicit",
    },
    "ignore": {
        "args": ["--ignore"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--ignore",
    },
    "needed": {
        "args": ["--needed"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--needed",
    },
    "overwrite": {
        "args": ["--overwrite"],
        "kwargs": {"nargs": "+"},
        "conflicts": [],
        "pacman_param": "--overwrite",
    },
}

REMOVE_ARGS = {
    "remove": {
        "args": ["-R", "--remove"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--remove",
    },
    "nodeps": {
        "args": ["-d", "--nodeps"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": [],
        "pacman_param": "--nodeps",
    },
    "assume_installed": {
        "args": ["--assume-installed"],
        "kwargs": {"nargs": "+", "dest": "assume_installed"},
        "conflicts": [],
        "pacman_param": "--assume_installed",
    },
    "dbonly": {
        "args": ["--dbonly"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--dbonly",
    },
    "noprogressbar": {
        "args": ["--noprogressbar"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--noprogressbar",
    },
    "noscriptlet": {
        "args": ["--noscriptlet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--noscriptlet",
    },
    "print_only": {
        "args": ["-p", "--print"],
        "kwargs": {"action": "store_true", "dest": "print_only"},
        "conflicts": [],
        "pacman_param": "--print",
    },
    "print_format": {
        "args": ["--print-format"],
        "kwargs": {"nargs": "+"},
        "conflicts": [],
        "pacman_param": "--print-format",
    },
    "cascade": {
        "args": ["-c", "--cascade"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--cascade",
    },
    "nosave": {
        "args": ["-n", "--nosave"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--nosave",
    },
    "recursive": {
        "args": ["-s", "--recursive"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--recursive",
    },
    "unneeded": {
        "args": ["-u", "--unneeded"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--unneeded",
    },
}


SYNC_ARGS = {
    "sync": {
        "args": ["-S", "--sync"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--sync",
    },
    "nodeps": {
        "args": ["-d", "--nodeps"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": [],
        "pacman_param": "--nodeps",
    },
    "assume_installed": {
        "args": ["--assume-installed"],
        "kwargs": {"nargs": "+", "dest": "assume_installed"},
        "conflicts": [],
        "pacman_param": "--assume_installed",
    },
    "dbonly": {
        "args": ["--dbonly"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--dbonly",
    },
    "noprogressbar": {
        "args": ["--noprogressbar"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--noprogressbar",
    },
    "noscriptlet": {
        "args": ["--noscriptlet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--noscriplet",
    },
    "print_only": {
        "args": ["-p", "--print"],
        "kwargs": {"action": "store_true", "dest": "print_only"},
        "conflicts": [],
        "pacman_param": "--print",
    },
    "print_format": {
        "args": ["--print-format"],
        "kwargs": {"nargs": "+"},
        "conflicts": [],
        "pacman_param": "--print-format",
    },
    "download_only": {
        "args": ["-w", "--downloadonly"],
        "kwargs": {"action": "store_true", "dest": "download_only"},
        "conflicts": [],
        "pacman_param": "--downloadonly",
    },
    "asdeps": {
        "args": ["--asdeps"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--asdeps",
    },
    "asexplicit": {
        "args": ["--asexplicit"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--asexplicit",
    },
    "ignore": {
        "args": ["--ignore"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--ignore",
    },
    "needed": {
        "args": ["--needed"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--needed",
    },
    "overwrite": {
        "args": ["--overwrite"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--overwrite",
    },
    "clean": {
        "args": ["-c", "--clean"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": ["refresh", "search", "sysupgrade"],
        "pacman_param": "--clean",
    },
    "groups": {
        "args": ["-g", "--groups"],
        "kwargs": {"action": "store_true"},
        "conflicts": ["info", "search", "sysupgrade"],
        "pacman_param": "--groups",
    },
    "info": {
        "args": ["-i", "--info"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--info",
    },
    "_list": {
        "args": ["-l", "--list"],
        "kwargs": {"action": "store_true", "dest": "_list"},
        "conflicts": [],
        "pacman_param": "--list",
    },
    "quiet": {
        "args": ["-q", "--quiet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--quiet",
    },
    "search": {
        "args": ["-s", "--search"],
        "kwargs": {"action": "store_true"},
        "conflicts": ["sysupgrade", "info", "clean"],
        "pacman_param": "--search",
    },
    "sysupgrade": {
        "args": ["-u", "--sysupgrade"],
        "kwargs": {"action": "store_true"},
        "conflicts": ["search", "clean", "info"],
        "pacman_param": "--sysupgrade",
    },
    "refresh": {
        "args": ["-y", "--refresh"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": ["clean"],
        "pacman_param": "--refresh",
    },
}


DATABASE_ARGS = {
    "database": {
        "args": ["-D", "--database"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--database",
    },
    "asdeps": {
        "args": ["--asdeps"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--asdeps",
    },
    "asexplicit": {
        "args": ["--asexplicit"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--asexplicit",
    },
    "check": {
        "args": ["-k", "--check"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--check",
    },
    "quiet": {
        "args": ["-q", "--quiet"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--quiet",
    },
}


QUERY_ARGS = {
    "query": {
        "args": ["-Q", "--query"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--query",
    },
    "changelog": {
        "args": ["-c", "--changelog"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--changelog",
    },
    "deps": {
        "args": ["-d", "--deps"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--deps",
    },
    "explicit": {
        "args": ["-e", "--explicit"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--explicit",
    },
    "group": {
        "args": ["-g", "--group"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--group",
    },
    "info": {
        "args": ["-i", "--info"],
        "kwargs": {"action": "store_true"},
        "conflcits": ["search"],
        "pacman_param": "--info",
    },
    "check": {
        "args": ["-k", "--check"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--check",
    },
    "list": {
        "args": ["-l", "--list"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--list",
    },
    "foreign": {
        "args": ["-m", "--foreign"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--foreign",
    },
    "native": {
        "args": ["-n", "--native"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--native",
    },
    "owns": {
        "args": ["-o", "--owns"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--owns",
    },
    "file": {
        "args": ["-p", "--file"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--file",
    },
    "quiet": {
        "args": ["-q", "--quiet"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--quiet",
    },
    "search": {
        "args": ["-s", "--search"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
        "pacman_param": "--search",
    },
    "unrequired": {
        "args": ["-t", "--unrequired"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--unrequired",
    },
}


FILES_ARGS = {
    "files": {
        "args": ["-F", "--files"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--files",
    },
    "refresh": {
        "args": ["-y", "--refresh"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": [],
        "pacman_param": "--refresh",
    },
    "list": {
        "args": ["-l", "--list"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--list",
    },
    "regex": {
        "args": ["-x", "--regex"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--regex",
    },
    "quiet": {
        "args": ["-q", "--quiet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--quiet",
    },
    "machinereadable": {
        "args": ["--machinereadable"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--machinereadable",
    },
}


DEPTEST_ARGS = {
    "deptest": {
        "args": ["-T", "--deptest"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--deptest",
    }
}


VERSION_ARGS = {
    "version": {
        "args": ["-V", "--version"],
        "kwargs": {
            "action": "store_true",
            "conflicts": [],
            "pacman_param": "--version",
        },
    }
}


NAY_ARGS = {
    "nay": {
        "args": ["-N", "--nay"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--sync",
    }
}

NAY_ARGS.update(SYNC_ARGS)

GETPKGBUILD_ARGS = {
    "GetPKGBUILD": {
        "args": ["-G", "--getpkgbuild"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "",
    }
}


GLOBAL_ARGS = {
    "dbpath": {
        "args": ["--dbpath"],
        "kwargs": {
            "nargs": "?",
            "default": "/var/lib/pacman",
        },
        "conflicts": [],
        "pacman_param": "--dbpath",
    },
    "root": {
        "args": ["--root"],
        "kwargs": {"nargs": "?", "default": "/"},
        "conflicts": [],
        "pacman_param": "--root",
    },
    "verbose": {
        "args": ["--verbose"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--verbose",
    },
    "arch": {"args": ["--arch"], "kwargs": {"nargs": 1}, "conflicts": []},
    "cachedir": {
        "args": ["--cachedir"],
        "kwargs": {
            "nargs": "?",
            "default": "/var/cache/pacman/pkg",
        },
        "conflicts": [],
        "pacman_param": "--cachedir",
    },
    "color": {
        "args": ["--color"],
        "kwargs": {"choices": ["always", "auto", "never"]},
        "conflicts": [],
        "pacman_param": "--color",
    },
    "config": {
        "args": ["--config"],
        "kwargs": {"nargs": "?", "default": "/etc/pacman.conf"},
        "conflicts": [],
        "pacman_param": "--config",
    },
    "debug": {"args": ["--debug"], "kwargs": {"action": "store_true"}, "conflicts": []},
    "gpgdir": {
        "args": ["--gpgdir"],
        "kwargs": {"nargs": "?", "default": "/etc/pacman.d/gnupg"},
        "conflicts": [],
        "pacman_param": "--gpgdir",
    },
    "hookdir": {
        "args": ["--hookdir"],
        "kwargs": {"nargs": "?", "default": "/etc/pacman.d/hooks"},
        "conflicts": [],
        "pacman_param": "--hookdir",
    },
    "logfile": {
        "args": ["--logfile"],
        "kwargs": {"nargs": "?", "default": "/var/log/pacman.log"},
        "conflicts": [],
        "pacman_param": "--logfile",
    },
    "noconfirm": {
        "args": ["--noconfirm"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--noconfirm",
    },
    "disable_download_timeout": {
        "args": ["--disable-download-timeout"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
        "pacman_param": "--disable-download-timeout",
    },
    "sysroot": {
        "args": ["--sysroot"],
        "kwargs": {"nargs": "?"},
        "conflicts": [],
        "pacman_param": "--sysroot",
    },
    "targets": {
        "args": ["targets"],
        "kwargs": {"nargs": "*"},
        "conflicts": [],
        "pacman_param": "--sysroot",
    },
}

OPERATIONS = {
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

OPERATION_MAPPER = {
    "remove": remove.Remove,
    "upgrade": operations.Operation,
    "sync": sync.Sync,
    "query": operations.Operation,
    "database": operations.Operation,
    "files": operations.Operation,
    "nay": sync.Nay,
    "getpkgbuild": operations.Operation,
    "deptest": operations.Operation,
    "version": operations.Operation,
}

ARG_MAPPER = {
    "remove": REMOVE_ARGS,
    "upgrade": UPGRADE_ARGS,
    "sync": SYNC_ARGS,
    "query": QUERY_ARGS,
    "database": DATABASE_ARGS,
    "files": FILES_ARGS,
    "nay": NAY_ARGS,
    "getpkgbuild": GETPKGBUILD_ARGS,
    "deptest": DEPTEST_ARGS,
    "version": VERSION_ARGS,
}


def _get_operation():
    valid_operations = []
    for arg in OPERATIONS:
        valid_operations.extend(OPERATIONS[arg]["args"])

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

    operation_parser = argparse.ArgumentParser(
        description="Argument parser for high level operations"
    )

    for operation in OPERATIONS:
        operation_parser.add_argument(
            *OPERATIONS[operation]["args"],
            **OPERATIONS[operation]["kwargs"],
        )

    operations = vars(operation_parser.parse_args(selected_operations))
    operation = [operation for operation in operations if operations[operation] is True]

    return operation[0]


def parse():
    operation = _get_operation()
    pacman_params = []
    unparsed = ARG_MAPPER[operation]
    unparsed.update(GLOBAL_ARGS)
    cls = OPERATION_MAPPER[operation]
    parser = argparse.ArgumentParser(exit_on_error=False)

    for arg in unparsed:
        parser.add_argument(
            *unparsed[arg]["args"],
            **unparsed[arg]["kwargs"],
        )

    parsed = parser.parse_args()
    parsed = vars(parsed)
    if operation == "nay":
        del parsed["sync"]
        parsed["nay"] = True
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
            pacman_params.append(parsed["targets"])

    parsed["pacman_params"] = pacman_params

    return {"operation": cls, "args": parsed}
