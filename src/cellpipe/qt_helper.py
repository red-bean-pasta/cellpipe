from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QWidget, QLayout, QFrame

ALIGN_LEFT_CENTER = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft


def lay_widgets(
        layout_type: type,
        *widgets: QWidget | tuple[QWidget, int]
) -> QWidget:
    container = QWidget()
    layout = layout_type(container)
    set_no_margin_spacing(layout)
    for w in widgets:
        if isinstance(w, tuple):
            layout.addWidget(w[0], w[1])
        else:
            layout.addWidget(w)
    return container


def set_no_margin_spacing(layout: QLayout | QFrame) -> None:
    if hasattr(layout, "setContentsMargins"):
        layout.setContentsMargins(0, 0, 0, 0)
    if hasattr(layout, "setSpacing"):
        layout.setSpacing(0)


def change_brightness(widget: QWidget, percentage: int):
    palette = widget.palette()
    color = palette.color(QPalette.ColorRole.Window).darker(percentage)  # 10% darker
    palette.setColor(QPalette.ColorRole.Window, color)
    widget.setAutoFillBackground(True)
    widget.setPalette(palette)