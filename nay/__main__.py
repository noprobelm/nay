from .args import parse_args
from .exceptions import ArgumentError


def main() -> None:
    try:
        args = parse_args()
        operation = args["operation"]
        operation = operation(**args["args"])
        operation.run()

    except KeyboardInterrupt:
        quit()
    except ArgumentError as err:
        print(err)
        quit()


if __name__ == "__main__":
    main()
