from .args import Args


def main():
    args = Args()
    operation = args["operation"](options=args["options"], args=args["args"])
    operation.run()


if __name__ == "__main__":
    main()
