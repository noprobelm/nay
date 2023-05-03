import sys
from ward import raises, test
from nay.args import Args
from nay.exceptions import ConflictingOperations, InvalidOperation
import nay.operations
import itertools


@test("Raises InvalidOperation if invalid operation is passed")
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("-X")
    with raises(InvalidOperation):
        Args()


@test("Raises ConflictingOperation if more than one recognized operation is passed")
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--sync")
    sys.argv.append("--query")
    with raises(ConflictingOperations):
        Args()


@test(
    "Raises InvalidOperation if one valid and one invalid operation is passed (in either order)"
)
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("-S")
    sys.argv.append("-X")
    with raises(InvalidOperation):
        Args()

    sys.argv = [sys.argv[0]]
    sys.argv.append("-X")
    sys.argv.append("-S")
    with raises(InvalidOperation):
        Args()


@test("Raises InvalidOperation if an invalid operation and arbitrary option are passed")
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--sync")
    sys.argv.append("-S")
    sys.argv.append("-X")
    with raises(InvalidOperation):
        Args()


@test("--sync or -S returns Args object with 'nay.operations.Sync' operation")
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--sync")
    args = Args()
    assert args["operation"] == nay.operations.Sync

    sys.argv = [sys.argv[0]]
    sys.argv.append("-S")
    assert args["operation"] == nay.operations.Sync


@test("--nay or -N returns Args object with 'nay.operations.Nay' operation")
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--nay")
    args = Args()
    assert args["operation"] == nay.operations.Nay

    sys.argv = [sys.argv[0]]
    sys.argv.append("-N")
    assert args["operation"] == nay.operations.Nay


@test(
    "--getpkgbuild or -G returns Args object with 'nay.operations.GetPKGBUILD' operation"
)
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--getpkgbuild")
    args = Args()
    assert args["operation"] == nay.operations.GetPKGBUILD

    sys.argv = [sys.argv[0]]
    sys.argv.append("-G")
    assert args["operation"] == nay.operations.GetPKGBUILD


@test("--upgrade or -U returns Args object with 'nay.operations.Upgrade' operation")
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--upgrade")
    args = Args()
    assert args["operation"] == nay.operations.Upgrade

    sys.argv = [sys.argv[0]]
    sys.argv.append("-G")
    assert args["operation"] == nay.operations.Upgrade


@test("--query or -Q returns Args object with 'nay.operations.Query' operation")
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--query")
    args = Args()
    assert args["operation"] == nay.operations.Query

    sys.argv = [sys.argv[0]]
    sys.argv.append("-Q")
    assert args["operation"] == nay.operations.Query


@test("--remove or -R returns Args object with 'nay.operations.Remove' operation")
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--remove")
    args = Args()
    assert args["operation"] == nay.operations.Remove

    sys.argv = [sys.argv[0]]
    sys.argv.append("-R")
    assert args["operation"] == nay.operations.Remove


@test(
    "A valid operation with an arbitrary number of options return an Args object reflecting as such"
)
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--remove")
    opts = ["--elkfjweklq", "-x", "-p", "--fklklejwkl", "--TlkjdnjnA"]
    sys.argv.extend(opts)
    args = Args()
    assert args["operation"] == nay.operations.Remove
    assert args["options"] == opts

    sys.argv = [sys.argv[0]]
    sys.argv.append("-R")
    opts = ["--elkfjweklq", "-x", "-p", "--fklklejwkl", "--TlkjdnjnA"]
    sys.argv.extend(opts)
    args = Args()
    assert args["operation"] == nay.operations.Remove
    assert args["options"] == opts


@test(
    "A valid operation with an arbitrary number of options and args returns an Args object reflecting as such"
)
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--remove")
    opts = ["--elkfjweklq", "-x", "-p", "--fklklejwkl", "--TlkjdnjnA"]
    sys.argv.extend(opts)
    args = Args()
    assert args["operation"] == nay.operations.Remove
    assert args["options"] == opts

    sys.argv = [sys.argv[0]]
    sys.argv.append("-R")
    sys.argv.extend(opts)
    args = Args()
    assert args["operation"] == nay.operations.Remove
    assert args["options"] == opts


@test(
    "A valid operation with an arbitrary number of options and args returns an Args object reflecting as such"
)
def _():
    sys.argv = [sys.argv[0]]
    sys.argv.append("--remove")
    opts = ["--elkfjweklq", "-x", "-p", "--fklklejwkl", "--TlkjdnjnA"]
    targets = ["9hfkjan", "fjealknge", "!3*#&Bbkjf"]
    sys.argv.extend(opts)
    sys.argv.extend(targets)
    args = Args()
    assert args["operation"] == nay.operations.Remove
    assert args["options"] == opts
    assert args["targets"] == targets

    sys.argv = [sys.argv[0]]
    sys.argv.append("-R")
    sys.argv.extend(opts)
    sys.argv.extend(targets)
    args = Args()
    assert args["operation"] == nay.operations.Remove
    assert args["options"] == opts
    assert args["targets"] == targets


@test("Operations, options, and arguments can be accepted in any order")
def _():
    operation = ["--remove"]
    opts = ["--elkfjweklq", "-x", "-p", "--fklklejwkl", "--TlkjdnjnA"]
    targets = ["9hfkjan", "fjealknge", "!3*#&Bbkjf"]
    argv = {"operation": operation, "opts": opts, "targets": targets}
    for permutation in list(itertools.permutations(argv.keys())):
        sys.argv = [sys.argv[0]]
        for val in permutation:
            sys.argv.extend(argv[val])
        args = Args()
        assert args["operation"] == nay.operations.Remove
        assert args["options"] == opts
        assert args["targets"] == targets
