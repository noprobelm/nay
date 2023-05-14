import sys
from .args import parse_args
from .exceptions import ArgumentError, ConfigReadError, HandleCreateError
from . import console


def main() -> None:
    try:
        args = parse_args()
        operation = args["operation"]
        operation = operation(**args["args"])
        operation.run()

    except KeyboardInterrupt:
        sys.exit()
    except (ArgumentError, HandleCreateError, ConfigReadError) as err:
        console.warn(str(err), exit=True)


if __name__ == "__main__":
    main()
