class ArgumentError(Exception):
    """Base class for exceptions in this module"""

    pass


class ALPMError(Exception):
    """Base class for exceptions encountered with libalpm/pyalpm"""

    pass


class ConfigReadError(Exception):
    """Class for handling pacman config read errors"""

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


class MissingTargets(ArgumentError):
    """
    Exception raised when no targets are passed to an operation requiring arguments.

    :param message: Explanation of the error
    :type message: str
    """


class PacmanError(ArgumentError):
    """
    Exception raised when pacman returns a non-zero return status code

    :param message: Explanation of the error
    :type message: str

    """


class HandleCreateError(ALPMError):
    pass
