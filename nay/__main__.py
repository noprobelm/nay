from .args import Args


def main():
    args = Args()
    operation = args["operation"](options=args["options"], args=args["args"])
    try:
        operation.run()
    except KeyboardInterrupt:
        quit()


if __name__ == "__main__":
    main()
