# -*- coding: utf-8 -*-

import logging
import logging.config

from PyQt5 import QtCore
from PyQt5.QtWidgets import (
        QApplication, QFrame, QPushButton, QProgressBar, QVBoxLayout)

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
            'level': 'DEBUG',
            'propagate': False
        },
    }
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger()

qtscheduler = qtthreadsafe.QtScheduler(QtCore)

class MainFrame(QFrame):
    def __init__(self):
        QFrame.__init__(self)

        trig_button = QPushButton('trig')
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)

        layout = QVBoxLayout()
        layout.addWidget(trig_button)
        layout.addWidget(progress_bar)
        self.setLayout(layout)


        trig = Subject()
        trig_button.released.connect(lambda : trig.on_next('aaa'))

        def wrap(_, last):
            out = (last) % 200 - 100
            return out

        def generate_sequence(x):
            stream = rx.interval(0.010).pipe(
                ops.scan(wrap, 0),
                ops.map(lambda i: -i if i < 0 else i),
                ops.take(101),
                )
            return stream

        disposable = trig.pipe(
            ops.map(generate_sequence),
            ops.switch_latest(),
            ops.sample(0.050),
            ops.observe_on(qtscheduler),
            ).subscribe(lambda i: progress_bar.setValue(i))


if __name__ == '__main__':
    qapp = QApplication([])
    main_frame = MainFrame()
    main_frame.show()
    qapp.exec_()
