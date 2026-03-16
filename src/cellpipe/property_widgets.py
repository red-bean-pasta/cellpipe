import shlex
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from pathlib import Path
from typing import Callable, Any, Self, Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QFrame,
    QFileDialog, QLineEdit, QPushButton, QScrollArea, QComboBox, QHBoxLayout, QVBoxLayout, QToolButton,
)

from cellpipe.qt_helper import set_no_margin_spacing, lay_widgets


@dataclass(slots=True)
class PropertyWidget:
    widget: QWidget
    get_value: Callable[[], Any]
    set_value: Callable[[Any], None]


class TokenLineEdit(QLineEdit):
    def text(self, /) -> list[str]:
        return shlex.split(super().text())

    def setText(self, text: str | list[str]) -> None:
        content = ""
        if text:
            text = [text] if isinstance(text, str) else text
            for token in text:
                content += f"'{token}' "
        super().setText(content)


class PickPathMode(StrEnum):
    PICK_FILE = "pick_file"
    PICK_DIR = "pick_dir"
    SAVE_FILE = "save_file"
    SAVE_DIR = "save_dir"


class PathPicker(QWidget):
    mode_chooser_map : dict[PickPathMode, Callable[[Self], str]] = {
        PickPathMode.PICK_FILE : lambda s: QFileDialog.getOpenFileName(s, "Choose file")[0],
        PickPathMode.PICK_DIR : lambda s: QFileDialog.getExistingDirectory(s, "Choose folder"),
        PickPathMode.SAVE_FILE : lambda s: QFileDialog.getSaveFileName(s, "Choose location to save")[0],
        PickPathMode.SAVE_DIR : lambda s: QFileDialog.getExistingDirectory(s, "Choose location to save")
    }

    def __init__(self, mode:PickPathMode, parent: QWidget | None = None):
        super().__init__(parent)
        self.mode = mode
        self.edit = QLineEdit()
        self.button = QPushButton("Browse...")
        self.button.clicked.connect(self.choose)
        layout = QHBoxLayout(self)
        set_no_margin_spacing(layout)
        layout.addWidget(self.edit)
        layout.addWidget(self.button)

    def choose(self) -> None:
        path = type(self).mode_chooser_map[self.mode](self)
        if path:
            self.set_value(path)

    def value(self) -> str:
        return self.edit.text().strip()

    def set_value(self, value: str | Path | None) -> None:
        if value is None:
            return
        self.edit.setText(str(value))


class DynamicPathPicker(PathPicker):
    def __init__(self, mode_picker: Callable[[], PickPathMode], parent: QWidget | None = None):
        super().__init__(mode_picker(), parent)
        self.mode_picker = mode_picker

    def choose(self) -> None:
        mode = self.mode_picker()
        path = type(self).mode_chooser_map[mode](self)
        if path:
            self.set_value(path)


class KeyValuesRow(QFrame):
    def __init__(
            self,
            key_placeholder: str | None = None,
            values_placeholder: str | None = None,
            parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.key_edit = QLineEdit()
        if key_placeholder:
            self.key_edit.setPlaceholderText(key_placeholder)
        self.values_edit = TokenLineEdit()
        if values_placeholder:
            self.values_edit.setPlaceholderText(values_placeholder)
        layout = QHBoxLayout(self)
        layout.addWidget(self.key_edit, 1)
        layout.addWidget(self.values_edit, 4)

    def get_value(self) -> tuple[str, list[str]] | None:
        key = self.key_edit.text().strip()
        values = self.values_edit.text()
        if not key or not values:
            return None
        return key, values

    def set_value(self, key: str, values: list[str] | str) -> None:
        if key:
            self.key_edit.setText(key)
        if values:
            self.values_edit.setText(values if isinstance(values, str) else " ".join(values))


class KeyValuesList(QWidget):
    def __init__(
            self,
            key_placeholder: str | None = None,
            values_placeholder: str | None = None,
            parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.key_placeholder = key_placeholder
        self.values_placeholder = values_placeholder
        self.rows: list[KeyValuesRow] = []
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)

        scroll = QScrollArea()
        scroll.setStyleSheet("QScrollArea { border: none; }")
        set_no_margin_spacing(scroll)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.rows_container)

        add_button = QPushButton("+")
        add_button.clicked.connect(self.add_empty_row)
        self.footer_container = QWidget()
        self.footer_layout = QHBoxLayout(self.footer_container)
        self.footer_layout.addWidget(add_button)

        root = QVBoxLayout(self)
        set_no_margin_spacing(root)
        root.addWidget(scroll, 1)
        root.addWidget(self.footer_container, alignment=Qt.AlignmentFlag.AlignRight)

        self.add_empty_row()

    def get_value(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for row in self.rows:
            if not (content := row.get_value()):
                continue
            key, values = content
            if key not in result:
               result[key] = values
            else:
                result[key].extend(values)
        return result

    def set_value(self, data: dict[str, str | list[str]]) -> None:
        for row in self.rows:
            self.remove_row(row)
        for key, values in data.items():
            self.add_row(key, values)
        if not self.rows:
            self.add_empty_row()

    def add_row(self, key: str, values: str | list[str]) -> None:
        row = KeyValuesRow(self.key_placeholder, self.values_placeholder)
        row.set_value(key, values)
        delete_button = QToolButton()
        delete_button.setText("ⓧ")
        container = lay_widgets(QHBoxLayout, (row, 1), delete_button)
        delete_button.clicked.connect(partial(self.remove_row, row, container))
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, container)
        self.rows.append(row)

    def add_empty_row(self) -> None:
        self.add_row("", "")

    def remove_row(self, row: KeyValuesRow, *widgets: QWidget) -> None:
        if row in self.rows:
            self.rows.remove(row)
            row.setParent(None)
            row.deleteLater()
        for w in widgets:
            w.setParent(None)
            w.deleteLater()
        if not self.rows:
            self.add_empty_row()

    def add_footer_widget(self, widget: QWidget, index: int = -1) -> None:
        self.footer_layout.insertWidget(index, widget)


def get_path_picker(
        mode: PickPathMode,
        default: str | Path | None = None,
        parent: QWidget | None = None
) -> PropertyWidget:
    p = PathPicker(mode, parent)
    if default:
        p.set_value(default)
    return PropertyWidget(
        p,
        get_value=p.value,
        set_value=p.set_value,
    )


def get_dynamic_path_picker(
        mode_picker: Callable[[], PickPathMode],
        default: str | Path | None = None,
        parent: QWidget | None = None
) -> PropertyWidget:
    p = DynamicPathPicker(mode_picker, parent)
    if default:
        p.set_value(default)
    return PropertyWidget(
        p,
        get_value=p.value,
        set_value=p.set_value,
    )


def get_key_values_list(
        key_placeholder: str | None = None,
        values_placeholder: str | None = None,
        default: dict[str, str | list[str]] = None,
        parent: QWidget | None = None
) -> PropertyWidget:
    l = KeyValuesList(key_placeholder, values_placeholder, parent)
    if default:
        l.set_value(default)
    return PropertyWidget(
        l,
        get_value=l.get_value,
        set_value=l.set_value,
    )


def get_combo_box(
        choices: Iterable[Any],
        default: Any | None = None
) -> PropertyWidget:
    widget = QComboBox()
    for choice in choices:
        widget.addItem(str(choice) if choice else "", choice)
    if default is not None and (idx := widget.findText(str(default))) > 0:
        widget.setCurrentIndex(idx)
    return PropertyWidget(
        widget=widget,
        get_value=lambda w=widget: w.currentData(),
        set_value=lambda value, w=widget: _combo_box_set_value(w, value),
    )


def _combo_box_set_value(widget: QComboBox, value: Any)-> None:
    i = widget.findData(value)
    if i < 0:
        i = widget.findText(str(value))
    if i >= 0:
        widget.setCurrentIndex(i)
