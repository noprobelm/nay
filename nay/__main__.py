from .args import Args


def main() -> None:
    args = Args()
    operation = args["operation"](options=args["options"], targets=args["targets"])
    try:
        operation.run()
    except KeyboardInterrupt:
        quit()


if __name__ == "__main__":
    main()
