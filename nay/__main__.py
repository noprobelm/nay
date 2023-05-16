import sys
from .args import parse_args
from .exceptions import ConfigReadError, HandleCreateError


def main() -> None:
    try:
        args = parse_args()
        operation = args["operation"]

        operation = operation(**args["args"])
        operation.run()

    except KeyboardInterrupt:
        sys.exit()
    except (HandleCreateError, ConfigReadError) as err:
        from .console import NayConsole

        console = NayConsole()
        console.warn(str(err), exit=True)


if __name__ == "__main__":
    main()
