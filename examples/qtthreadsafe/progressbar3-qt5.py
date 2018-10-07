# -*- coding: utf-8 -*-

import logging
import logging.config

from PyQt5 import QtCore
from PyQt5.QtWidgets import (
        QApplication, QFrame, QPushButton, QProgressBar, QVBoxLayout)

import rx
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

        qtscheduler = qtthreadsafe.QtScheduler(QtCore)

        trig = Subject()
        trig_button.released.connect(lambda : trig.on_next('aaa'))

        def wrap(_, last):
            out = (last) % 200 - 100
            return out

        def generate_sequence(x):
            stream = (rx.Observable
                      .interval(10, rx.concurrency.new_thread_scheduler)
#                      .take(10)
                      .scan(wrap, 0)
                      .map(lambda i: -i if i < 0 else i)
#                      .take(100)
                      )
            return stream

        disposable = (trig
                      .select_switch(generate_sequence)
#                      .do_action(lambda i: print(i))
#                      .sample(50)
#                      .observe_on(qtscheduler)
                      .subscribe(lambda i: progress_bar.setValue(i))
                      )


if __name__ == '__main__':
    qapp = QApplication([])
    main_frame = MainFrame()
    main_frame.show()
    qapp.exec_()
