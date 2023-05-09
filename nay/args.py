import pathlib
import sys
import argparse
import re
from dataclasses import dataclass
from typing import Iterable

from . import operations
from . import sync
from .exceptions import ConflictingOperations, InvalidOperation, ConflictingOptions


UPGRADE_ARGS = {
    "upgrade": {
        "args": ["-U", "--upgrade"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "nodeps": {
        "args": ["-d", "--nodeps"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": [],
    },
    "assume-installed": {
        "args": ["--assume-installed"],
        "kwargs": {"nargs": "+", "type": str},
        "conflicts": [],
    },
    "dbonly": {
        "args": ["--dbonly"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "noprogressbar": {
        "args": ["--noprogressbar"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "noscriptlet": {
        "args": ["--noscriptlet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "print": {
        "args": ["-p, --print"],
        "kwargs": {"action": "store_true", "dest": "print_only"},
        "conflicts": [],
    },
    "--print-format": {
        "args": ["--print-format"],
        "kwargs": {"nargs": "?"},
        "conflicts": [],
    },
    "downloadonly": {
        "args": ["-w", "--downloadonly"],
        "kwargs": {"action": "store_true", "dest": "download_only"},
        "conflicts": [],
    },
    "asdeps": {
        "args": ["--aspdeps"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "asexplicit": {
        "args": ["--asexplicit"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "ignore": {
        "args": ["--ignore"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "needed": {
        "args": ["--needed"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "overwrite": {"args": ["--overwrite"], "kwargs": {"nargs": "+"}, "conflicts": []},
}

REMOVE_ARGS = {
    "remove": {
        "args": ["-R", "--remove"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "nodeps": {
        "args": ["-d", "--nodeps"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": [],
    },
    "assume-installed": {
        "args": ["--assume-installed"],
        "kwargs": {"nargs": 1},
        "conflicts": [],
    },
    "dbonly": {
        "args": ["--dbonly"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "noprogressbar": {
        "args": ["--noprogressbar"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "noscriptlet": {
        "args": ["--noscriptlet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "print": {
        "args": ["-p, --print"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "--print-format": {
        "args": ["--print-format"],
        "kwargs": {"nargs": "?"},
        "conflicts": [],
    },
}


SYNC_ARGS = {
    "sync": {
        "args": ["-S", "--sync"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "nodeps": {
        "args": ["-d", "--nodeps"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": [],
    },
    "assume_installed": {
        "args": ["--assume-installed"],
        "kwargs": {"nargs": "?"},
        "conflicts": [],
    },
    "dbonly": {
        "args": ["--dbonly"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "noprogressbar": {
        "args": ["--noprogressbar"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "noscriptlet": {
        "args": ["--noscriptlet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "print": {
        "args": ["-p, --print"],
        "kwargs": {"action": "store_true", "dest": "print_only"},
        "conflicts": [],
    },
    "--print-format": {
        "args": ["--print-format"],
        "kwargs": {"nargs": "?"},
        "conflicts": [],
    },
    "downloadonly": {
        "args": ["-w", "--downloadonly"],
        "kwargs": {"action": "store_true", "dest": "download_only"},
        "conflicts": [],
    },
    "asdeps": {
        "args": ["--asdeps"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "asexplicit": {
        "args": ["--asexplicit"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "ignore": {
        "args": ["--ignore"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "needed": {
        "args": ["--needed"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "overwrite": {
        "args": ["--overwrite"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "clean": {
        "args": ["-c", "--clean"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": ["refresh", "search", "sysupgrade"],
    },
    "groups": {
        "args": ["-g", "--groups"],
        "kwargs": {"action": "store_true"},
        "conflicts": ["info", "search", "sysupgrade"],
    },
    "info": {
        "args": ["-i", "--info"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "list": {
        "args": ["-l", "--list"],
        "kwargs": {"action": "store_true", "dest": "_list"},
        "conflicts": [],
    },
    "quiet": {
        "args": ["-q", "--quiet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "search": {
        "args": ["-s", "--search"],
        "kwargs": {"action": "store_true"},
        "conflicts": ["sysupgrade", "info", "clean"],
    },
    "sysupgrade": {
        "args": ["-u", "--sysupgrade"],
        "kwargs": {"action": "store_true"},
        "conflicts": ["search", "clean", "info"],
    },
    "refresh": {
        "args": ["-y", "--refresh"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": ["clean"],
    },
}


DATABASE_ARGS = {
    "database": {
        "args": ["-D", "--database"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "asdeps": {
        "args": ["--asdeps"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "asexplicit": {
        "args": ["--asexplicit"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "check": {
        "args": ["-k", "--check"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "quiet": {
        "args": ["-q", "--quiet"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
}


QUERY_ARGS = {
    "query": {
        "args": ["-Q", "--query"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "changelog": {
        "args": ["-c", "--changelog"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "deps": {
        "args": ["-d", "--deps"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "explicit": {
        "args": ["-e", "--explicit"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "group": {
        "args": ["-g", "--group"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "info": {
        "args": ["-i", "--info"],
        "kwargs": {"action": "store_true"},
        "conflcits": ["search"],
    },
    "check": {
        "args": ["-k", "--check"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "list": {
        "args": ["-l", "--list"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "foreign": {
        "args": ["-m", "--foreign"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "native": {
        "args": ["-n", "--native"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "owns": {
        "args": ["-o", "--owns"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "file": {
        "args": ["-p", "--file"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "quiet": {
        "args": ["-q", "--quiet"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "search": {
        "args": ["-s", "--search"],
        "kwargs": {"action": "store_true"},
        "conflcits": [],
    },
    "unrequired": {
        "args": ["-t", "--unrequired"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
}


FILES_ARGS = {
    "files": {
        "args": ["-F", "--files"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "refresh": {
        "args": ["-y", "--refresh"],
        "kwargs": {"action": "count", "default": 0},
        "conflicts": [],
    },
    "list": {
        "args": ["-l", "--list"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "regex": {
        "args": ["-x", "--regex"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "quiet": {
        "args": ["-q", "--quiet"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "machinereadable": {
        "args": ["--machinereadable"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
}


DEPTEST_ARGS = {
    "deptest": {
        "args": ["-T", "--deptest"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    }
}


VERSION_ARGS = {
    "version": {
        "args": ["-V", "--version"],
        "kwargs": {"action": "store_true", "conflicts": []},
    }
}


NAY_ARGS = {
    "nay": {
        "args": ["-N", "--nay"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    }
}

GETPKGBUILD_ARGS = {
    "GetPKGBUILD": {
        "args": ["-G", "--getpkgbuild"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
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
    },
    "root": {
        "args": ["--root"],
        "kwargs": {"nargs": "?", "default": "/"},
        "conflicts": [],
    },
    "verbose": {
        "args": ["--verbose"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "arch": {"args": ["--arch"], "kwargs": {"nargs": 1}, "conflicts": []},
    "cachedir": {
        "args": ["--cachedir"],
        "kwargs": {
            "nargs": "?",
            "default": "/var/cache/pacman/pkg",
        },
        "conflicts": [],
    },
    "color": {
        "args": ["--color"],
        "kwargs": {"choices": ["always", "auto", "never"]},
        "conflicts": [],
    },
    "config": {
        "args": ["--config"],
        "kwargs": {"nargs": "?", "default": "/etc/pacman.conf"},
        "conflicts": [],
    },
    "debug": {"args": ["--debug"], "kwargs": {"action": "store_true"}, "conflicts": []},
    "gpgdir": {
        "args": ["--gpgdir"],
        "kwargs": {"nargs": "?", "default": "/etc/pacman.d/gnupg"},
        "conflicts": [],
    },
    "hookdir": {
        "args": ["--hookdir"],
        "kwargs": {"nargs": "?", "default": "/etc/pacman.d/hooks"},
        "conflicts": [],
    },
    "logfile": {
        "args": ["--logfile"],
        "kwargs": {"nargs": "?", "default": "/var/log/pacman.log"},
        "conflicts": [],
    },
    "noconfirm": {
        "args": ["--noconfirm"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "disable_download_timeout": {
        "args": ["--disable-download-timeout"],
        "kwargs": {"action": "store_true"},
        "conflicts": [],
    },
    "sysroot": {"args": ["--sysroot"], "kwargs": {"nargs": "?"}, "conflicts": []},
    "targets": {"args": ["targets"], "kwargs": {"nargs": "*"}, "conflicts": []},
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
    "remove": operations.Operation,
    "upgrade": operations.Operation,
    "sync": sync.Sync,
    "query": operations.Operation,
    "database": operations.Operation,
    "files": operations.Operation,
    "nay": operations.Operation,
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
    unparsed = ARG_MAPPER[operation]
    unparsed.update(GLOBAL_ARGS)
    cls = OPERATION_MAPPER[operation]
    parser = argparse.ArgumentParser()

    for arg in unparsed:
        parser.add_argument(
            *unparsed[arg]["args"],
            **unparsed[arg]["kwargs"],
        )

    parsed = vars(parser.parse_args())
    del parsed[operation]
    for arg in parsed:
        if parsed[arg]:
            for other in parsed:
                if parsed[other]:
                    if other in unparsed[arg]["conflicts"]:
                        raise ConflictingOptions(
                            f"error: invalid option: '{arg}' and '{other}' may not be used together"
                        )

    return {"operation": cls, "args": parsed}
