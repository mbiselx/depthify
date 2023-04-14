'''
file defining some GUI utilites specific to this project
'''

import typing

import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets


def deleteItemsOfLayout(layout: QtWidgets.QLayout):
    # stolen from https://stackoverflow.com/a/45790404
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
            else:
                deleteItemsOfLayout(item.layout())

        layout.deleteLater()


class ColorBar(QtWidgets.QFrame):
    """
    A widget that displays a color bar representing a given color map.

    Parameters:
    -----------
    parent: Optional[QtWidgets.QWidget] = None
        The parent widget.
    orientation: QtCore.Qt.Orientations = QtCore.Qt.Orientation.Vertical
        The orientation of the color bar.

    """

    def __init__(self,
                 parent: typing.Optional[QtWidgets.QWidget] = None,
                 orientation: QtCore.Qt.Orientations = QtCore.Qt.Orientation.Vertical
                 ) -> None:
        super().__init__(parent)
        self._orientation = orientation
        self.setColorMap(pg.colormap.get('Viridis'))  # type: ignore
        self.setMinimumSize(QtCore.QSize(10, 10))

    def setOrientation(self, orientation: QtCore.Qt.Orientations):
        '''Sets the orientation of the color bar.'''
        self._orientation = orientation
        if orientation == QtCore.Qt.Orientation.Vertical:
            self.setMaximumHeight(2**16)
            self.setMaximumWidth(50)
        else:
            self.setMaximumHeight(50)
            self.setMaximumWidth(2**16)
        self.update()

    def colormap(self) -> pg.ColorMap:
        '''Returns the current colormap used by the color bar.'''
        return self._cmap

    def setColorMap(self, cmap: pg.ColorMap):
        '''sets the colormap used by the color bar.'''
        self._cmap = cmap

    def getColor(self, value: int, span: tuple[int, int] = (0, 255)) -> QtGui.QColor:
        '''Returns the QtGui.QColor corresponding to the given value in the given span of the colormap'''
        return QtGui.QColor(self._cmap.mapToQColor(1 - (value - min(span))/(max(span) - min(span))))

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        '''Called whenever the ColorBar is drawn'''
        super().paintEvent(event)

        with QtGui.QPainter(self) as p:
            p: QtGui.QPainter
            p.setBrush(
                self._cmap.getBrush(
                    span=(0, self.width() if self._orientation ==
                          QtCore.Qt.Orientation.Horizontal else self.height()),
                    orientation='horizontal' if self._orientation == QtCore.Qt.Orientation.Horizontal else 'vertical'
                )
            )
            p.drawRect(self.contentsRect())


class DepthSlider(QtWidgets.QWidget):
    """
    A Qt widget that combines a slider, a spin box, and a color bar to represent a value ranging from 0 to 255.

    Signals:
        - valueChanged(int): emitted when the value of the slider changes.

    Methods:
        - __init__(self, parent=None, orientation=QtCore.Qt.Orientation.Vertical, flags=QtCore.Qt.WindowType.Widget):
            Constructs a DepthSlider with the specified orientation and flags.
        - setOrientation(self, orientation: QtCore.Qt.Orientations):
            Sets the orientation of the DepthSlider to the specified value.
        - wheelEvent(self, a0: QtGui.QWheelEvent) -> None:
            Overrides the wheelEvent of QWidget to forward the event to the slider.
        - value(self) -> int:
            Returns the current value of the slider.
        - setValue(self, value: int):
            Sets the current value of the slider to the specified value.
        - color(self, value: Optional[float] = None) -> QtGui.QColor:
            Returns the color corresponding to the current value of the slider. If a float value is provided, returns the color
            corresponding to that value on the color bar.
    """
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent: typing.Optional[QtWidgets.QWidget] = None,
                 orientation: QtCore.Qt.Orientations = QtCore.Qt.Orientation.Vertical,
                 flags: typing.Union[QtCore.Qt.WindowFlags, QtCore.Qt.WindowType] = QtCore.Qt.WindowType.Widget) -> None:
        super().__init__(parent, flags)

        self._slider = QtWidgets.QSlider(orientation, self)
        self._slider.setMinimum(0)
        self._slider.setMaximum(255)

        self._colorbar = ColorBar(self, orientation)

        self._number = QtWidgets.QSpinBox(self)
        self._number.setMinimum(0)
        self._number.setMaximum(255)
        self._number.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._number.setButtonSymbols(
            QtWidgets.QSpinBox.ButtonSymbols.NoButtons)

        self._number.valueChanged.connect(self._slider.setValue)
        self._number.valueChanged.connect(self.valueChanged.emit)
        self._slider.valueChanged.connect(self._number.setValue)
        self._slider.valueChanged.connect(self.valueChanged.emit)

        self.setOrientation(orientation)

    def setOrientation(self, orientation: QtCore.Qt.Orientations):
        '''Sets the orientation of the DepthSlider to the specified value.'''
        self._orientation = orientation
        self._slider.setOrientation(orientation)
        self._colorbar.setOrientation(orientation)

        deleteItemsOfLayout(self.layout())
        if self.layout() is not None:
            return

        # re-do layout
        if self._orientation == QtCore.Qt.Orientation.Vertical:
            slider_layout = QtWidgets.QHBoxLayout()
        else:
            slider_layout = QtWidgets.QVBoxLayout()
        slider_layout.addWidget(self._slider)
        slider_layout.addWidget(self._colorbar)

        if self._orientation == QtCore.Qt.Orientation.Vertical:
            layout = QtWidgets.QVBoxLayout()
        else:
            layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._number)
        layout.addLayout(slider_layout)
        self.setLayout(layout)

        self.update()

    def wheelEvent(self, a0: QtGui.QWheelEvent) -> None:
        '''forward any mousewheel event to the slider'''
        return self._slider.wheelEvent(a0)

    def value(self) -> int:
        '''returns the value of the depth slider'''
        return self._slider.value()

    def setValue(self, value: int):
        '''set the value of the depth slider'''
        self._slider.setValue(value)
        self._number.setValue(value)

    def color(self, value: typing.Optional[float] = None) -> QtGui.QColor:
        '''get the color corresponding to a given value. if no value is provided, get the current color'''
        span = (self._slider.minimum(), self._slider.maximum())
        if value is None:
            return self._colorbar.getColor(self._slider.value(), span)
        return self._colorbar.getColor(int(value), span)
