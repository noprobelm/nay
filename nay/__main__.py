from .args import parse_args
from .exceptions import ArgumentError
from datetime import datetime


def main() -> None:
    try:
        start = datetime.now()
        args = parse_args()
        operation = args["operation"]
        operation = operation(**args["args"])
        operation.run()
        end = datetime.now()
        print(f"Operation completed in {end - start}")

    except KeyboardInterrupt:
        quit()
    except ArgumentError as err:
        print(err)
        quit()


if __name__ == "__main__":
    main()
