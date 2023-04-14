'''
file defining a few generic GUI utilites
'''

import typing
import logging

from PyQt5 import QtCore, QtGui, QtWidgets


class ImageViewer(QtWidgets.QFrame):
    """
    A widget for displaying images within a GUI application.

    Methods:
        image() -> QtGui.QImage:
            Returns the current image being displayed in the widget.

        setImage(image: QtGui.QImage | str):
            Sets the image to be displayed in the widget.

        clear():
            Clears the currently displayed image from the widget.
    """

    def __init__(self,
                 parent: typing.Optional[QtWidgets.QWidget] = None,
                 flags: typing.Union[QtCore.Qt.WindowFlags, QtCore.Qt.WindowType] = QtCore.Qt.WindowType.Widget) -> None:
        super().__init__(parent, flags)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._image = QtGui.QImage()
        self._scaled_image = QtGui.QImage()  # caching the scaled image
        self._rect = QtCore.QRect()
        self.setContentsMargins(*4*[9])

    def minimumSizeHint(self) -> QtCore.QSize:
        '''Returns the minimum size hint for the widget.'''
        return super().minimumSizeHint().expandedTo(QtCore.QSize(250, 250))

    def image(self) -> QtGui.QImage:
        '''Returns the current image being displayed in the widget.'''
        return self._image

    def setImage(self, image: QtGui.QImage | str):
        '''Sets the image to be displayed in the widget.'''
        if isinstance(image, str):
            self._image = QtGui.QImage(image)
        elif isinstance(image, QtGui.QImage):
            self._image = image
        else:
            raise TypeError(
                f"expected an QImage or an image path, not `{type(image)}`")
        self.clearCache()
        self.update()

    def clear(self):
        '''Clears the currently displayed image from the widget.'''
        self._image = QtGui.QImage()
        self.clearCache()
        self.update()

    def clearCache(self, drawnow: bool = False):
        '''clear internal cache of the scaled image. This forces the image to be re-scaled on next draw'''
        self._scaled_image = QtGui.QImage()
        if drawnow:
            self.repaint()

    def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
        # clear the cached scaled image
        self.clearCache()
        return super().resizeEvent(a0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        '''Paints the widget and displays the current image, if any.'''
        super().paintEvent(event)

        # can we even draw something
        if self._image.isNull():
            return

        # re-create scaled image if cache has been cleared
        if self._scaled_image.isNull():
            self._scaled_image = self._image.scaled(
                self.contentsRect().size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )

            self._rect.setSize(self._scaled_image.size())
            self._rect.moveCenter(self.contentsRect().center())

        # paint the scaled image
        with QtGui.QPainter(self) as p:
            p: QtGui.QPainter
            p.drawImage(self._rect, self._scaled_image)


class ClickableImageViewer(ImageViewer):
    clicked = QtCore.pyqtSignal(QtCore.QPoint)
    clicked_img = QtCore.pyqtSignal(QtCore.QPointF)

    def _px_to_img(self, point: QtCore.QPoint | QtCore.QPointF) -> QtCore.QPointF:
        '''takes a point in pixel coordinates and returns the corresponding point in image coordinates'''
        return QtCore.QPointF(
            point.x()/self._rect.width()*self.image().size().width(),
            point.y()/self._rect.height()*self.image().size().height()
        )

    def _img_to_px(self, point: QtCore.QPoint | QtCore.QPointF) -> QtCore.QPointF:
        '''takes a point in image coordinates and returns the corresponding point in pixel coordinates'''
        return QtCore.QPointF(
            point.x()/self.image().size().width()*self._rect.width(),
            point.y()/self.image().size().height()*self._rect.height()
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        '''emits the `clicked` and `clicked_img` signals with the pixel and image coordinates of the click, respectively'''
        if not self.image().isNull():
            self.clicked.emit(event.pos())
            self.clicked_img.emit(self._px_to_img(
                event.pos() - self._rect.topLeft()))
