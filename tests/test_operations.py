from ward import raises, test
import nay.operations
from nay.exceptions import (
    ConflictingOptions,
    MissingTargets,
    PacmanError,
    InvalidOption,
)


@test(
    "Wrapper class raises PacmanError when invalid options are passed to a class/subclass instance"
)
def _():
    opts = ["--elkfjweklq", "-x", "-p", "--fklklejwkl", "--TlkjdnjnA"]
    with raises(PacmanError):
        operation = nay.operations.Query(options=opts, targets=[])
        operation.run()


@test("Sync class raises InvalidOption when invalid options are passed to the class")
def _():
    opts = ["--elkfjweklq", "-x", "-p", "--fklklejwkl", "--TlkjdnjnA"]
    with raises(InvalidOption):
        nay.operations.Sync(options=opts, targets=[])

    with raises(InvalidOption):
        nay.operations.Nay(options=opts, targets=[])


@test(
    "Sync class raises ConflictingOptions when conflicting options are passed to the class"
)
def _():
    opts = ["--info", "--sysupgrade"]
    with raises(ConflictingOptions):
        nay.operations.Sync(options=opts, targets=[])


@test(
    "Sync class raises MissingTargets when options requiring a target are passed with no targets present"
)
def _():
    with raises(MissingTargets):
        operation = nay.operations.Sync(options=[], targets=[])
        operation.run()
