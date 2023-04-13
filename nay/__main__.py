from .args import Args
from . import operations


def main():
    args = Args()
    operation = args["operation"](args)
    operation.run()


if __name__ == "__main__":
    main()
