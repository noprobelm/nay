from .args import Args
from .exceptions import ArgumentError


def main() -> None:
    try:
        args = Args()
        operation = args["operation"](targets=args["targets"], **args["kwargs"])
        operation.run()
    except KeyboardInterrupt:
        quit()
    except ArgumentError as err:
        print(err)
        quit()


if __name__ == "__main__":
    main()
