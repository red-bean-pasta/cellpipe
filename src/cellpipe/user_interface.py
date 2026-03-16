import argparse
import html
import logging
from argparse import ArgumentParser
from functools import partial
from typing import Callable

from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QScrollArea, QHBoxLayout, QVBoxLayout, QPushButton, QTextEdit,
)

from cellpipe import ui_arg
from cellpipe.meta import MODULE_NAME
from cellpipe.qt_helper import set_no_margin_spacing
from cellpipe.ui_arg import ArgWidget


logger = logging.getLogger(__name__)


class LogSignaler(QObject):
    on_log_update = Signal(str, int)


class QtLogHandler(logging.Handler):
    def __init__(self, signaler: LogSignaler):
        super().__init__()
        self.signaler = signaler

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self.signaler.on_log_update.emit(msg, record.levelno)


class WorkerThread(QThread):
    finish_signal = Signal()

    def __init__(self, runner: Callable[[], None]):
        super().__init__()
        self.runner = runner

    def run(self):
        try:
            self.runner()
        except Exception as e:
            logging.exception("Runner failed")
        finally:
            self.finish_signal.emit()


class RunButton(QPushButton):
    def __init__(
            self,
            parser: ArgumentParser,
            arg_widgets: list[ArgWidget],
            hook: Callable[[argparse.Namespace], None],
            parent: QWidget | None = None,
    ):
        super().__init__("Run", parent)
        self._parser = parser
        self._arguments = arg_widgets
        self._hook = hook
        self._worker: WorkerThread | None = None
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        try:
            arg_list = _get_flatten_properties(self._arguments)
            logger.info(f"Running with arguments: {str(arg_list)}")
            parsed = self._parser.parse_args(arg_list)
        except argparse.ArgumentError as e:
            logger.error(str(e))
            return
        except Exception:
            logger.exception("Unexpected error during arguments parsing")
            return
        self.setEnabled(False)
        self._worker = WorkerThread(partial(self._hook, parsed))
        self._worker.finish_signal.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self) -> None:
        self._worker = None
        self.setEnabled(True)


class MainWindow(QMainWindow):
    def __init__(
            self,
            parser: argparse.ArgumentParser,
            runner: Callable[[argparse.Namespace], None]
    ):
        super().__init__()
        self.setWindowTitle(MODULE_NAME)
        self._set_initial_size()

        content, _ = _build_window(parser, runner)
        self.setCentralWidget(content)

    def _set_initial_size(self) -> None:
        width = self.screen().availableGeometry().width() * 0.4
        height = 11 / 10 * width
        self.resize(int(width), int(height))


def _build_window(
        parser: argparse.ArgumentParser,
        runner: Callable[[argparse.Namespace], None]
) -> tuple[QWidget, list[ArgWidget]]:
    # Right pane
    right_pane = QWidget()
    right_layout = QVBoxLayout(right_pane)
    set_no_margin_spacing(right_layout)

    main = QWidget()
    main_layout = QVBoxLayout(main)
    arguments: list[ArgWidget] = []
    for group in parser._action_groups:
        built = ui_arg.build_group_widget(group)
        if not built:
            continue
        w, a = built
        main_layout.addWidget(w)
        arguments.extend(a)
    scroll = QScrollArea()
    set_no_margin_spacing(scroll)
    scroll.setWidgetResizable(True)
    scroll.setWidget(main)

    run_button = RunButton(parser, arguments, runner)
    run_button.setStyleSheet("""
        QPushButton {
            min-width: 85px;
            min-height: 30px;
            margin: 7px;
        }
    """)

    right_layout.addWidget(scroll)
    right_layout.addWidget(run_button, alignment=Qt.AlignmentFlag.AlignRight)

    # Left pane
    console = _build_log_console_and_hook()

    # Root
    root = QWidget()
    root_layout = QHBoxLayout(root)
    set_no_margin_spacing(root_layout)
    root_layout.addWidget(console, 4)
    root_layout.addWidget(right_pane, 7)

    return root, arguments


def _build_log_console_and_hook() -> QWidget:
    console = QTextEdit()
    console.setReadOnly(True)
    console.setPlaceholderText("The runtime log will appear here :)")

    log_signaler = LogSignaler()
    log_signaler.on_log_update.connect(partial(_append_console_log, console))

    log_handler = QtLogHandler(log_signaler)
    if logging.getLogger().handlers:
        log_handler.setFormatter(logging.getLogger().handlers[0].formatter)
    logging.getLogger().addHandler(log_handler)

    return console


def _get_flatten_properties(arguments: list[ArgWidget]) -> list[str]:
    result: list[str] = []
    for widget in arguments:
        if args := widget.get_arguments():
            result.extend(args)
    return result


_log_colors = {
    logging.DEBUG: QColor("gray"),
    logging.INFO: QColor("black"),
    logging.WARNING: QColor("orange"),
    logging.ERROR: QColor("red"),
    logging.CRITICAL: QColor("darkred"),
}
def _append_console_log(console: QTextEdit, msg: str, levelno: int) -> None:
    color = _log_colors.get(levelno, QColor("black"))
    console.append(f'<span style="color:{color.name()}">{html.escape(msg)}</span>')