class ALPMError(Exception):
    """Base class for exceptions encountered with libalpm/pyalpm"""

    pass


class HandleCreateError(ALPMError):
    pass


class ConfigReadError(Exception):
    """Class for handling pacman config read errors"""

    pass


class MissingTargets(Exception):
    pass
