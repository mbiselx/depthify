import os
import sys
import typing
import logging

import numpy as np
from scipy.interpolate import griddata

import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

from depthify.gui_utils import *
from depthify.depthify_utils import *


class ImageWithPoints(ClickableImageViewer):
    def __init__(self,
                 parent: typing.Optional[QtWidgets.QWidget] = None,
                 flags: typing.Union[QtCore.Qt.WindowFlags, QtCore.Qt.WindowType] = QtCore.Qt.WindowType.Widget) -> None:
        super().__init__(parent, flags)
        self._points: list[
            tuple[QtCore.QPoint | QtCore.QPointF, QtGui.QColor]] = list()

    def addPoint(self, point: QtCore.QPoint | QtCore.QPointF, color: QtGui.QColor | None = None):
        self._points.append((point, color))
        self.update()

    def undoPoint(self):
        try:
            self._points.pop()
            self.update()
        except IndexError:  # don't crash if empty
            pass

    def clearPoints(self):
        self._points = list()
        self.update()

    def clear(self):
        self.clearPoints()
        return super().clear()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        # paint image
        super().paintEvent(event)

        # paint points over it
        with QtGui.QPainter(self) as p:
            p: QtGui.QPainter
            for pt, col in self._points:
                p.setPen(QtGui.QPen(col or QtCore.Qt.GlobalColor.red, 5))
                p.setBrush(col or QtCore.Qt.GlobalColor.red)
                p.drawPoint(self._img_to_px(pt) + self._rect.topLeft())
                # p.drawEllipse(QtCore.QRectF(
                #     self._img_to_px(pt), QtCore.QSizeF(5, 5)))


class DepthViewer(ImageViewer):
    """
    A widget for displaying a depth map based on user-specified points.

    Methods:
        setImageSize(size: QtCore.QSize) -> None:
            Sets the size of the image to be displayed.

        setColorMap(cmap: pg.ColorMap) -> None:
            Sets the colormap to be used to display the depth map.

        addPoint(point: Union[QtCore.QPoint, QtCore.QPointF], depth: float) -> None:
            Adds a point with a corresponding depth value to the depth map.
            The depth map is created using the current set of points and displayed
            using the current colormap.

        clearPoints() -> None:
            Removes all points from the depth map.

        clear() -> None:
            Removes all points from the depth map and clears the displayed image.

    """

    def __init__(self, parent: typing.Optional[QtWidgets.QWidget] = None,
                 flags: typing.Union[QtCore.Qt.WindowFlags,
                                     QtCore.Qt.WindowType] = QtCore.Qt.WindowType.Widget) -> None:
        super().__init__(parent, flags)
        self._points: list[tuple[tuple[float, float], float]] = list()
        self._image_size = QtCore.QSize(50, 50)
        self._cmap: pg.ColorMap = pg.colormap.get("viridis")  # type: ignore
        self._depth_map: typing.Optional[np.ndarray] = None

    def setImageSize(self, size: QtCore.QSize):
        '''Sets the size of the image to be displayed.'''
        self._image_size = size

    def setColorMap(self, cmap: pg.ColorMap):
        '''Sets the colormap to be used to display the depth map.'''
        self._cmap = cmap

    def addPoint(self, point: QtCore.QPoint | QtCore.QPointF, depth: float):
        '''
        Adds a point with a corresponding depth value to the depth map.
        '''
        self._points.append(((point.x(), point.y()), depth))
        self.updateDepthMap()

    def undoPoint(self):
        '''Undo the last point which has been added'''
        try:
            self._points.pop()
            self.updateDepthMap()
        except IndexError:  # don't crash if empty
            pass

    def clearPoints(self):
        '''Removes all points from the depth map.'''
        self._points = list()
        self.updateDepthMap()

    def clear(self):
        '''Removes all points from the depth map and clears the displayed image.'''
        self.clearPoints()
        return super().clear()

    def updateDepthMap(self):
        '''
        The depth map is created using the current set of points and displayed
        using the current colormap.
        '''
        # check if we can even plot anything yet
        if len(self._points) < 4:  # minimum 4 points for interpolation
            self._depth_map = 255 * np.ones((self._image_size.height(),
                                            self._image_size.width()),
                                            np.uint8)
            tmp_img = pg.makeQImage(self._depth_map, transpose=False)
            self.setImage(tmp_img)
            return

        # grab the points and depths from the current array
        points, depths = zip(*self._points)
        points = np.array(points)

        # Get the image dimensions
        height, width = self._image_size.height(), self._image_size.width()

        # Create a grid of points to interpolate depth values
        x, y = np.meshgrid(np.arange(width), np.arange(height))
        z = griddata(points, depths, (x, y), fill_value=255)

        # clip image values to allowable values
        self._depth_map = np.clip(z, 0, 255, out=z).astype(np.uint8)

        # Create a depth map image, using the colormap
        # NOTE : the colormap has the B and R channels inverted, for some reason
        depth_image = self._cmap.map(1 - (z/255))
        depth_image = depth_image[:, :, [2, 1, 0, 3]]  # type: ignore
        depth_image = pg.makeQImage(depth_image, transpose=False)

        # Set the depth map image
        self.logger.debug("updating depth image")
        self.setImage(depth_image)

        self.update()

    def depthmap(self) -> np.ndarray | None:
        return self._depth_map


class MainWindow(QtWidgets.QMainWindow):
    ACCEPTED_FILETYPES = ('jpg', 'jpeg', 'png')

    def __init__(self,
                 parent: typing.Optional[QtWidgets.QWidget] = None,
                 flags: typing.Union[QtCore.Qt.WindowFlags, QtCore.Qt.WindowType] = QtCore.Qt.WindowType.Widget) -> None:
        super().__init__(parent, flags)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._filepath: str | None = None

        # allow dragging & dropping files
        self.setAcceptDrops(True)

        # set window always on top (easier for debug)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)

        # the different widgets
        self._image_viewer = ImageWithPoints(self)
        self._slider = DepthSlider(self)
        self._depth_viewer = DepthViewer(self)
        self._depth_viewer.setColorMap(self._slider._colorbar.colormap())
        self._depth_image_viewer = ImageViewer(self)
        self._toolbar = QtWidgets.QToolBar('toolbar', self)

        # functionality
        self._image_viewer.clicked_img.connect(self.addPoint)

        self._openImageAction = QtWidgets.QAction('&Open image')
        self._openImageAction.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_DialogOpenButton))
        self._openImageAction.setShortcut(
            QtCore.Qt.Modifier.CTRL + QtCore.Qt.Key.Key_O)
        self._openImageAction.triggered.connect(self.openImage)
        self._toolbar.addAction(self._openImageAction)

        self._saveDepthImageAction = QtWidgets.QAction('&Save depth image')
        self._saveDepthImageAction.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton))
        self._saveDepthImageAction.setShortcut(
            QtCore.Qt.Modifier.CTRL + QtCore.Qt.Key.Key_S)
        self._saveDepthImageAction.triggered.connect(self.saveDepthImage)
        self._toolbar.addAction(self._saveDepthImageAction)

        self._toolbar.addSeparator()

        self._undoPointAction = QtWidgets.QAction('&Undo last point')
        self._undoPointAction.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_LineEditClearButton))
        self._undoPointAction.setShortcut(
            QtCore.Qt.Modifier.CTRL + QtCore.Qt.Key.Key_Z)
        self._undoPointAction.triggered.connect(self.undoPoint)
        self._toolbar.addAction(self._undoPointAction)

        self._clearPointsAction = QtWidgets.QAction('&Clear points')
        self._clearPointsAction.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_DialogDiscardButton))
        self._clearPointsAction.setShortcut(
            QtCore.Qt.Modifier.CTRL + QtCore.Qt.Key.Key_R)
        self._clearPointsAction.triggered.connect(self.clearPoints)
        self._toolbar.addAction(self._clearPointsAction)

        self._toolbar.addSeparator()

        self._exportDepthMapAction = QtWidgets.QAction('&Export depth map')
        self._exportDepthMapAction.setIcon(self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton))
        self._exportDepthMapAction.triggered.connect(self.exportDepthMap)
        self._toolbar.addAction(self._exportDepthMapAction)

        self.addActions(self._toolbar.actions())

        # do layout
        self.setCentralWidget(self._image_viewer)
        self.addToolBar(self._toolbar)

        dw_slider = QtWidgets.QDockWidget('Depth Slider')
        dw_slider.setWidget(self._slider)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dw_slider)

        def fix_slider_orientation(dwa: QtCore.Qt.DockWidgetAreas):
            '''update the slider's orientation to fit the dockarea it has been placed into'''
            if dwa in (QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, QtCore.Qt.DockWidgetArea.TopDockWidgetArea):
                self._slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
            else:
                self._slider.setOrientation(QtCore.Qt.Orientation.Vertical)
        dw_slider.dockLocationChanged.connect(fix_slider_orientation)

        dw_depth = QtWidgets.QDockWidget('Depth Map View')
        dw_depth.setWidget(self._depth_viewer)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dw_depth)

        dw_img = QtWidgets.QDockWidget('Depth Image View')
        dw_img.setWidget(self._depth_image_viewer)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dw_img)
        self.tabifyDockWidget(dw_depth, dw_img)

    def __enter__(self):
        self.show()
        return self

    def __exit__(self, *args):
        pass

    def sizeHint(self) -> QtCore.QSize:
        return super().sizeHint().expandedTo(QtCore.QSize(700, 500))

    def openImage(self):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Open image',
            directory='.',
        )
        # maybe user canceled ?
        if filepath is None or filepath == '':
            return

        self.setImage(filepath)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        '''accept any image files'''

        # dragged from VSCode or file browser
        if event.mimeData().hasText():
            text = event.mimeData().text()
            text = text.removeprefix('file:///')
            if os.path.isfile(text) and text.casefold().endswith(self.ACCEPTED_FILETYPES):
                return event.accept()

        # ignore everything else
        event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        '''what do if image file is given'''
        self.setImage(event.mimeData().text().removeprefix('file:///'))

    def wheelEvent(self, a0: QtGui.QWheelEvent) -> None:
        # all wheel events should be forwarded to the slider
        return self._slider.wheelEvent(a0)

    def setImage(self, filepath: str):
        self.logger.debug(f"opening `{filepath}`")

        # clear old data
        self.clear()

        # set new image
        self._filepath = filepath
        self._image_viewer.setImage(filepath)
        self._depth_viewer.setImageSize(self._image_viewer.image().size())

    def addPoint(self, point: QtCore.QPoint | QtCore.QPointF, dist: int | None = None):
        if dist is None:  # get current values from slider
            dist = self._slider.value()
            color = self._slider.color()
        else:
            color = self._slider.color(dist)

        # add the point the the 2D image
        self._image_viewer.addPoint(point, color)
        self._depth_viewer.addPoint(point, dist)
        self.createDepthImage()

    def undoPoint(self):
        self._image_viewer.undoPoint()
        self._depth_viewer.undoPoint()
        self.createDepthImage()

    def clearPoints(self):
        self._image_viewer.clearPoints()
        self._depth_viewer.clear()
        self.createDepthImage()

    def clear(self):
        self._image_viewer.clear()
        self._depth_viewer.clear()
        self._depth_image_viewer.clear()

    def createDepthImage(self):
        # retrieve the image
        img = self._image_viewer.image()
        img.convertTo(QtGui.QImage.Format.Format_Grayscale8)
        ptr = img.bits()
        ptr.setsize(img.height()*img.width())
        img = np.frombuffer(ptr, np.uint8).reshape(  # type: ignore
            img.height(), img.width())

        # retrieve depth map
        dpth = self._depth_viewer.depthmap()
        if dpth is None:
            dpth = 255*np.ones_like(img)

        # null dimension, because we need three channels
        null = np.zeros_like(dpth)

        # create the full 3-channel image
        depth_image: QtGui.QImage = pg.makeQImage(
            np.stack((img, dpth, null), axis=2),
            transpose=False
        )

        self._depth_image_viewer.setImage(depth_image)

    def exportDepthMap(self):
        if self._filepath is None:
            QtWidgets.QErrorMessage(self).showMessage(
                'Cannot export depth map.\n'
                'No image file is currently set.'
            )
            return

        # try to guess the filepath the user will want
        filepath, suffix = self._filepath.rsplit('.', 1)
        newfilepath = filepath + '_map.' + suffix

        # confirm the filepath with the user
        newfilepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'save depth map to:',
            directory=newfilepath,
        )

        # maybe user canceled ?
        if newfilepath is None or newfilepath == '':
            return

        # retrieve the depth map
        depth_image: QtGui.QImage = pg.makeQImage(
            self._depth_viewer.depthmap(),
            transpose=False
        )

        # save
        self.logger.debug(f"exporting depth map to {newfilepath}")
        depth_image.save(newfilepath)

    def saveDepthImage(self):
        if self._filepath is None:
            QtWidgets.QErrorMessage(self).showMessage(
                'Cannot save depth image.\n'
                'No image file is currently set.'
            )
            return

        # try to guess the filepath the user will want
        filepath, suffix = self._filepath.rsplit('.', 1)
        newfilepath = filepath + '_depth.' + suffix

        # confirm the filepath with the user
        newfilepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'save depth image to:',
            directory=newfilepath,
        )

        # maybe user canceled ?
        if newfilepath is None or newfilepath == '':
            return

        # save
        self.logger.debug(f"exporting depth map to {newfilepath}")
        self._depth_image_viewer.image().save(newfilepath)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('Depthify')

    with MainWindow() as mw:
        sys.exit(app.exec())
