# -*- coding: utf-8 -*-

import logging
import logging.config
import math

from PyQt5 import QtCore
from PyQt5.QtWidgets import (
        QApplication, QFrame, QPushButton, QProgressBar, QVBoxLayout)

from PyQt5.QtGui import (QPainter)
from PyQt5 import QtWidgets
from PyQt5 import QtGui

import rx
from rx import operators as ops
from rx.subjects import Subject
from rx.concurrency.mainloopscheduler import qtthreadsafe

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': True
        },
        'Rx': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': False
        },
    }
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger()

class RenderArea(QFrame):
    mouse_press = QtCore.pyqtSignal()

    def __init__(self):
        QFrame.__init__(self)
        self.setBackgroundRole(QtGui.QPalette.Base)
        self.setAutoFillBackground(True)
        self._xy = (0.8, 0.0)

    def draw_coordinates(self, xy):
        self._xy = xy
        self.update()

    def paintEvent(self, event):

        qsize = self.size()
        global_size = (qsize.width(), qsize.height())

        x, y = self._xy

        rect_wh = (
                int(0.2 * global_size[0]),
                int(0.2 * global_size[1]),
                )

        cropped_size = (
                int(global_size[0] - rect_wh[0]),
                int(global_size[1] - rect_wh[1]),
                )

        rect_xy = (
                int(x * cropped_size[0] ),
                int(y * cropped_size[1] ),
                )


        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(*rect_xy, *rect_wh), 10, 10)
        pen = QtGui.QPen(QtCore.Qt.black, 8)
        p.setPen(pen)
        p.fillPath(path, QtCore.Qt.red)
        p.drawPath(path)

    def sizeHint(self):
        return QtCore.QSize(400, 400)

    def minimumSizeHint(self):
        return QtCore.QSize(400, 200)

    def mousePressEvent(self, event):
        self.mouse_press.emit()


new_thread_scheduler = rx.concurrency.NewThreadScheduler()

class MainFrame(QFrame):
    def __init__(self):
        QFrame.__init__(self)
        layout = QVBoxLayout()
        render_area = RenderArea()
        trig_button = QPushButton('trig')
        layout.addWidget(render_area)
        layout.addWidget(trig_button)
        self.setLayout(layout)

        trig = rx.subjects.Subject()
        trig_button.released.connect(lambda : trig.on_next(0))
        render_area.mouse_press.connect(lambda : trig.on_next(0))

        period = 1/60.0
        frequency = 0.5

        pulsation = 2 * math.pi * frequency

        def calculate_xy(t):
            x = 0.5 * math.sin(pulsation * t) + 0.5
            y = 0.5 * math.cos(pulsation * t) + 0.5
            return (x, y)

        def produce_coordinates(*args):
            coordinates = rx.interval(period, new_thread_scheduler).pipe(
                ops.scan(lambda last, _: last + period, 0.0),
                ops.map(calculate_xy),
                )
            return coordinates

        disposable = trig.pipe(
            ops.start_with(0),
            ops.map(produce_coordinates),
            ops.switch_latest(),
            ops.observe_on(qtthreadsafe.QtScheduler(QtCore)),
            ).subscribe(render_area.draw_coordinates),


if __name__ == '__main__':
    qapp = QApplication([])
    main_frame = MainFrame()
    main_frame.show()
    qapp.exec_()
