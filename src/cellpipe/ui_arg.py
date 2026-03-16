import argparse
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable, Any, Iterable

import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QLabel, QCheckBox, QSpinBox, QDoubleSpinBox, QToolButton, QMessageBox,
    QHBoxLayout, QVBoxLayout, QGridLayout,
)

from cellpipe import property_widgets
from cellpipe.property_widgets import PropertyWidget, PickPathMode
from cellpipe.qt_helper import set_no_margin_spacing


@dataclass(slots=True)
class ArgWidget:
    widget : PropertyWidget
    _action : argparse.Action
    _get_arguments : Callable[[str, Any], list[str] | None]

    def get_arguments(self) -> list[str] | None:
        flag = self._action.option_strings[0]
        values = self.widget.get_value()
        return self._get_arguments(flag, values)


class InfoButton(QToolButton):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setText("ⓘ")
        self.label=""
        self.help_text=""
        self.setAutoRaise(True)
        self.setToolTip(self.help_text)
        self.clicked.connect(self.show_help)

    def show_help(self) -> None:
        if self.help_text:
            QMessageBox.information(
                self.parent(),
                self.label,
                self.help_text,
            )

    def set_help(self, label: str, text: str) -> None:
        self.label = label
        self.help_text = text
        self.setToolTip(f"<div style='width: 250px;'>{text}</div>")


def attach_widgets(parser: argparse.ArgumentParser) -> None:
    source_format = parser._option_string_actions["--source-format"]
    choices = [None]
    choices.extend(list(source_format.choices))
    format_combo_box = _get_choices_widget(source_format, None, choices)
    _wrap(
        source_format,
        widget=format_combo_box
    )

    source = parser._option_string_actions["--source"]
    _wrap(
        source,
        widget=_get_dynamic_path_picker_widget(source, None, _get_source_picker_mode(format_combo_box.widget, ["10x-mtx"]))
    )

    marker = parser._option_string_actions["--marker"]
    _wrap(
        marker,
        widget=_get_key_value_list_widget(marker, None, "Cell type", "Genes separated by blank space")
    )

    output = parser._option_string_actions["--output"]
    _wrap(
        output,
        widget=_get_path_picker_widget(output, None, PickPathMode.SAVE_DIR)
    )
    save_h5ad = parser._option_string_actions["--save-h5ad"]
    _wrap(
        save_h5ad,
        widget=_get_path_picker_widget(save_h5ad, None, PickPathMode.SAVE_FILE)
    )

    celltypist_model = parser._option_string_actions["--celltypist-model"]
    _wrap(
        celltypist_model,
        widget=_get_path_picker_widget(celltypist_model, None, PickPathMode.SAVE_FILE)
    )


def _wrap(
        action: argparse.Action,
        *,
        widget: ArgWidget | None,
        **kwargs
) -> argparse.Action:
    """
    One can explicitly set widget to None to achieve CLI-only argument
    :param action:
    :param widget:
    :param kwargs:
    :return:
    """
    props = {
        "widget": widget,
        **kwargs
    }
    for k, v in props.items():
        setattr(action, k, v)
    return action


def build_group_widget(group: argparse._ArgumentGroup) -> tuple[QWidget, list[ArgWidget]] | None:
    v_container = QWidget()
    stack = QVBoxLayout(v_container)

    title = _make_group_title(group)

    f_container = QWidget()
    grid = QGridLayout(f_container)
    set_no_margin_spacing(grid)

    arg_widgets: list[ArgWidget] = []
    for i, a in enumerate(group._group_actions):
        if a.dest == "help":
            continue
        arg_widget = _get_arg_widget(a)
        if not arg_widget:
            continue
        label = QLabel(_get_action_label(a))
        widget = _attach_info_button(a, arg_widget.widget.widget)
        grid.addWidget(label, i, 0)
        grid.addWidget(widget, i, 1)
        arg_widgets.append(arg_widget)

    stack.addWidget(title)
    stack.addWidget(f_container)

    if not arg_widgets:
        return None
    return v_container, arg_widgets


def _make_group_title(action: argparse._ArgumentGroup) -> QWidget:
    label = QLabel(action.title)
    _set_font(label, delta=3, bold=True)

    if not action.description:
        return label

    description = QLabel(action.description)
    _set_font(description, delta=-3, bold=False)
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.addWidget(label)
    layout.addWidget(description)
    return container


def _get_arg_widget(action: argparse.Action) -> ArgWidget | None:
    return action.widget if hasattr(action, "widget") else _infer_widget(action)


def _get_action_label(action: argparse.Action, add_required_star: bool = True) -> str:
    label = action.option_strings[-1].replace("-", " ").strip()
    if add_required_star and action.required:
        label += "*"
    return label


def _infer_widget(action: argparse.Action) -> ArgWidget:
    default = None if action.default is argparse.SUPPRESS else action.default

    if action.type is bool or isinstance(action, argparse._StoreFalseAction | argparse._StoreTrueAction):
        constructor = _get_store_bool_widget
    elif action.type is int or issubclass(action.type or str, np.unsignedinteger):
        constructor = _get_int_widget
    elif action.type is float:
        constructor = _get_float_widget
    elif action.choices:
        constructor = _get_choices_widget
    elif action.type is Path:
        constructor = partial(_get_path_picker_widget, mode=PickPathMode.PICK_FILE)
    else:
        constructor = _get_token_text_widget

    return constructor(action, default)


def _attach_info_button(action: argparse.Action, widget: QWidget) -> QWidget:
    text = action.help
    if not text:
        return widget

    label = _get_action_label(action)
    button = InfoButton(parent=widget.parent())
    button.set_help(label, text)

    if hasattr(widget, "add_footer_widget"):
        widget.add_footer_widget(button)
        return widget

    container = QWidget(widget.parent())
    layout = QHBoxLayout(container)
    layout.addWidget(widget, 1)
    layout.addWidget(button)
    return container


def _get_store_bool_widget(
        action: argparse.Action,
        default: bool | None,
) -> ArgWidget:
    widget = QCheckBox()

    if default is not None:
        checked = bool(default)
    elif isinstance(action, argparse._StoreTrueAction):
        checked = False
    elif isinstance(action, argparse._StoreFalseAction):
        checked = True
    else:
        checked = False
    widget.setChecked(checked)

    return ArgWidget(
        PropertyWidget(
            widget=widget,
            get_value=lambda w=widget: w.isChecked(),
            set_value=lambda value, w=widget: w.setChecked(bool(value))
        ),
        _action=action,
        _get_arguments=lambda flag, value: [flag] if value else None
    )


def _get_int_widget(
        action: argparse.Action,
        default: int | np.unsignedinteger | None,
) -> ArgWidget:
    widget = QSpinBox()
    widget.setRange(0 if action.type is np.unsignedinteger else -2 ** 31, 2 ** 31 - 1)
    if default:
        widget.setValue(int(default))
    return ArgWidget(
        PropertyWidget(
            widget=widget,
            get_value=lambda w=widget: w.value(),
            set_value=lambda value, w=widget: w.setValue(int(value)),
        ),
        _action=action,
        _get_arguments=_convert_typical_options
    )


def _get_float_widget(
        action: argparse.Action,
        default: float | None,
) -> ArgWidget:
    widget = QDoubleSpinBox()
    widget.setRange(-1e9, 1e9)
    widget.setDecimals(4)
    widget.setSingleStep(0.1)
    if default:
        widget.setValue(float(default))
    return ArgWidget(
        PropertyWidget(
            widget=widget,
            get_value=lambda w=widget: w.value(),
            set_value=lambda value, w=widget: w.setValue(float(value)),
        ),
        _action=action,
        _get_arguments=_convert_typical_options
    )


def _get_choices_widget(
        action: argparse.Action,
        default: Any,
        choices: Iterable[Any] | None = None
) -> ArgWidget:
    if not choices:
        choices = action.choices
    return ArgWidget(
        property_widgets.get_combo_box(choices, default),
        _action=action,
        _get_arguments=_convert_typical_options
    )


def _get_token_text_widget(
        action: argparse.Action,
        default: str | list[str] | None,
) -> ArgWidget:
    widget = property_widgets.TokenLineEdit()
    if default:
        widget.setText(default)

    def _get_arguments(flag: str, value: list[str]) -> list[str] | None:
        if not value:
            return None
        args = [flag]
        args.extend(value)
        return args
    return ArgWidget(
        PropertyWidget(
            widget=widget,
            get_value=lambda w=widget: w.text(),
            set_value=lambda value, w=widget: w.setText(value),
        ),
        _action=action,
        _get_arguments=_get_arguments
    )


def _get_path_picker_widget(
        action: argparse.Action,
        default: str | None,
        mode: PickPathMode
) -> ArgWidget:
    return ArgWidget(
        property_widgets.get_path_picker(mode, default),
        _action=action,
        _get_arguments=_convert_typical_options
    )


def _get_dynamic_path_picker_widget(
        action: argparse.Action,
        default: str | None,
        mode_picker: Callable[[], PickPathMode]
) -> ArgWidget:
    return ArgWidget(
        property_widgets.get_dynamic_path_picker(mode_picker, default),
        _action=action,
        _get_arguments=_convert_typical_options
    )


def _get_key_value_list_widget(
        action: argparse.Action,
        default: dict[str, str | list[str]] | None,
        key_placeholder: str,
        value_placeholder: str
) -> ArgWidget:
    def _get_arguments(flag: str, value: dict[str, list[str]] | None) -> list[str] | None:
        if not value:
            return None
        result = []
        for k, v in value.items():
            result.append(flag)
            result.append(k)
            result.extend(v)
        return result
    return ArgWidget(
        property_widgets.get_key_values_list(key_placeholder, value_placeholder, default),
        action,
        _get_arguments
    )


def _get_source_picker_mode(
        combo_box: PropertyWidget,
        folder_options: list[str]
) -> Callable[[], PickPathMode]:
    def inner_pick() -> PickPathMode:
        if combo_box.get_value() in folder_options:
            return PickPathMode.PICK_DIR
        return PickPathMode.PICK_FILE

    return inner_pick


def _convert_typical_options(flag: str, value: Any) -> list[str] | None:
    if not value and value != 0:
        return None
    return [flag, str(value)]


def _set_font(widget, *, delta=0, bold=False):
    font = widget.font()
    font.setPointSize(font.pointSize() + delta)
    font.setBold(bold)
    widget.setFont(font)
