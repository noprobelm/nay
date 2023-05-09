from .args import parse
from .exceptions import ArgumentError


def main() -> None:
    try:
        args = parse()
        operation = args["operation"]
        operation = operation(**args["args"])
        print(operation)
    except KeyboardInterrupt:
        quit()
    except ArgumentError as err:
        print(err)
        quit()


if __name__ == "__main__":
    main()
