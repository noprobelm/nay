from .args import Args
from .exceptions import ArgumentError


def main() -> None:
    try:
        args = Args()
        operation = args["operation"](options=args["options"], targets=args["targets"])
    except ArgumentError as err:
        print(err)
        quit()
    try:
        operation.run()
    except KeyboardInterrupt:
        quit()


if __name__ == "__main__":
    main()
