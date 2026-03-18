import logging
import sys

import scanpy

from cellpipe.meta import MODULE_NAME, PYSIDE6_INSTALLED
from cellpipe import arg_parser
from cellpipe.core import run


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    if len(sys.argv) > 1:
        logger.info("Command line argument provided. Running in CLI mode...")
        args = arg_parser.parser.parse_args()
        raise SystemExit(run(args))

    if not PYSIDE6_INSTALLED:
        logger.info(f"Falling back to CLI mode: GUI dependency PySide6 not installed")
        args = arg_parser.parser.parse_args()
        raise SystemExit(run(args))

    logger.info("No command line argument provided. Trying to run with UI interface...")
    from PySide6.QtWidgets import QApplication
    from cellpipe.ui_arg import attach_widgets
    from cellpipe.user_interface import MainWindow
    app = QApplication(sys.argv)
    attach_widgets(arg_parser.parser)
    win = MainWindow(arg_parser.parser, run)
    win.show()
    sys.exit(app.exec())


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,  # to avoid Numba log explosion
        format="%(levelname)s: %(name)s: %(message)s",
    )
    logging.getLogger(MODULE_NAME).setLevel(logging.DEBUG)
    scanpy.settings.verbosity = "debug"


if __name__ == "__main__":
    main()