'''allows execution of the module'''

import sys

from PyQt5.QtWidgets import QApplication

from depthify.depthify import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)

    with MainWindow() as mw:
        sys.exit(app.exec())
