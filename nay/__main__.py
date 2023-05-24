import sys

from .args import OperationParams
from .exceptions import ConfigReadError, HandleCreateError, MissingTargets


def main() -> None:
    try:
        op_params = OperationParams()
        op_cls = op_params["op_cls"]
        kwargs = op_params["kwargs"]

        operation = op_cls(**kwargs)
        operation.run()

    except KeyboardInterrupt:
        sys.exit()
    except (HandleCreateError, ConfigReadError, MissingTargets) as err:
        from .console import NayConsole

        console = NayConsole()
        console.warn(str(err), exit=True)


if __name__ == "__main__":
    main()
