import logging

from rx.disposable import Disposable
from rx.disposable import SingleAssignmentDisposable, CompositeDisposable
from rx.concurrency.schedulerbase import SchedulerBase
# from rx import config

log = logging.getLogger("Rx")
log2 = logging.getLogger("Rx.qtschedulersafe")

"""
The scheduler posts custom events (RxEvent) to a handler (RxHandler) which
lives on the same qthread as the QApplication or QCoreApplication. RxEvents
are posted using the postEvent mechanism (thread-safe). These events hold
timing informations and the function to be invoked.

Custom Qt classes (RxEvent & RxHandler) are defined on runtime to avoid import
issues.

Limitations:
    Disposables can't be disposed after the qt main loop exit (i.e. return
    of app.exec_()).

"""

glob_post_function = None

SCHEDULE_NOW = 'Rx.SCHEDULE_NOW'            # args: (invoke_action, timer_ptr)
SCHEDULE_LATER = 'Rx.SCHEDULE_LATER'        # args; (invoke_action, timer_ptr, duetime)
SCHEDULE_PERIODIC = 'Rx.SCHEDULE_PERIODIC'  # args; (invoke_action, timer_ptr, period)
DISPOSE = 'Rx.DISPOSE'                      # args: (timer_ptr,)


def create_RxEvent_class(QtCore, qevent_type):
    """
    Creates a custom QEvent class with the specified type.
    """

    class RxEvent(QtCore.QEvent):
        def __init__(self, scheduling, args):
            QtCore.QEvent.__init__(self, qevent_type)
            self.args = args
            self.scheduling = scheduling

    return RxEvent


def create_RxHandler_class(QtCore):

    class RxHandler(QtCore.QObject):
        """
        Handles rx events posted on the qt application main loop and
        triggers QTimers in the main thread.
        """

        def __init__(self, parent):
            QtCore.QObject.__init__(self, parent)

            def schedule_now(args):
                invoke_action, timer_ptr = args
                invoke_action()

            def schedule_later(args):
                invoke_action, timer_ptr, duetime = args
                qtimer = QtCore.QTimer()
                qtimer.setSingleShot(True)
                qtimer.timeout.connect(invoke_action)
                timer_ptr[0] = qtimer
                qtimer.start(duetime)

            def schedule_periodic(args):
                invoke_action, timer_ptr, period = args
                qtimer = QtCore.QTimer()
                qtimer.setSingleShot(False)
                qtimer.setInterval(period)
                qtimer.timeout.connect(invoke_action)
                timer_ptr[0] = qtimer
                qtimer.start()

            def dispose(args):
                timer_ptr, = args
                try:
                    timer_ptr[0].stop()
                    log2.debug('dispose timer_ptr:{}'.format(timer_ptr))
                except AttributeError:
                    log2.debug('dispose skipped for '
                               'timer_ptr:{}'.format(timer_ptr))

            self.dispatcher = {
                    SCHEDULE_NOW: schedule_now,
                    SCHEDULE_LATER: schedule_later,
                    SCHEDULE_PERIODIC: schedule_periodic,
                    DISPOSE: dispose
                    }

        def event(self, event):
            scheduling = event.scheduling
            args = event.args

            self.dispatcher[scheduling](args)
            return True

    return RxHandler


def QtScheduler(QtCore):
    """A scheduler for a PyQt4/PyQt5/PySide event loop."""
    global glob_post_function

    # protect the creation of Handler from different threads
    # with config['concurrency'].RLock():
    if glob_post_function is None:

        # Get the current QApplication running
        qapp = QtCore.QCoreApplication.instance()

        if qapp is None:
            etext = (
                "Unable to get instance of QCoreAplication. "
                "A QCoreApplication/QApplication must be instanciate "
                "before creating a rx QtScheduler "
                "(e.g. qapp = QtWidgets.QApplication([])."
                )
            raise RuntimeError(etext)

        # create Handler & RxEvent classes
        qevent_type = QtCore.QEvent.registerEventType()
        RxEvent = create_RxEvent_class(QtCore, qevent_type)
        Handler = create_RxHandler_class(QtCore)
        log.info('QEvent type [{}] reserved for Rx.'.format(qevent_type))

        # create Handler on the qapplication thread
        current_handler = Handler(None)
        current_handler.moveToThread(qapp.thread())
#            current_handler.setParent(qapp)
        log.info('Rx Handler successfully created.')

        def post_function(scheduling, args):
            QtCore.QCoreApplication.postEvent(
                     current_handler,
                     RxEvent(scheduling, args),
                     )

        glob_post_function = post_function

    return _QtScheduler(glob_post_function)


class _QtScheduler(SchedulerBase):
    """A scheduler for a PyQt4/PyQt5/PySide event loop."""

    def __init__(self, post_function):
        self._post = post_function

    def schedule(self, action, state=None):
        """Schedules an action to be executed."""
        disposable = SingleAssignmentDisposable()

        log2.debug('shedule')

        def invoke_action():
#            disposable.disposable = action(scheduler, state)
            disposable.disposable = self.invoke_action(action, state)

        timer_ptr = [None]

        def dispose():
            self._post(DISPOSE, (timer_ptr,))

        self._post(SCHEDULE_NOW, (invoke_action, timer_ptr))

        return CompositeDisposable(disposable, Disposable(dispose))

    def schedule_relative(self, duetime, action, state=None):
        """Schedules an action to be executed after duetime.

        Keyword arguments:
        duetime -- {timedelta} Relative time after which to execute the action.
        action -- {Function} Action to be executed.

        Returns {Disposable} The disposable object used to cancel the scheduled
        action (best effort)."""
        duetime = self.to_relative(duetime)

        if duetime == 0:
            return self.schedule(action, state)

        disposable = SingleAssignmentDisposable()

        log2.debug('shedule relative duetime: {}'.format(duetime))

        def invoke_action():
            disposable.disposable = self.invoke_action(action, state)

        timer_ptr = [None]

        def dispose():
            self._post(DISPOSE, (timer_ptr,))

        self._post(SCHEDULE_LATER, (invoke_action, timer_ptr, duetime))

        return CompositeDisposable(disposable, Disposable(dispose))

    def schedule_absolute(self, duetime, action, state=None):
        """Schedules an action to be executed at duetime.

        Keyword arguments:
        duetime -- {datetime} Absolute time after which to execute the action.
        action -- {Function} Action to be executed.

        Returns {Disposable} The disposable object used to cancel the scheduled
        action (best effort)."""

        duetime = self.to_datetime(duetime)
        return self.schedule_relative(duetime, action, state)

    def schedule_periodic(self, period, action, state=None):
        """Schedules a periodic piece of work to be executed in the Qt
        mainloop.

        Keyword arguments:
        period -- Period in milliseconds for running the work periodically.
        action -- Action to be executed.
        state -- [Optional] Initial state passed to the action upon the first
            iteration.

        Returns the disposable object used to cancel the scheduled recurring
        action (best effort)."""
        log2.debug('shedule periodic')

        disposable = SingleAssignmentDisposable()

        periodic_state = [state]

        def invoke_action():
            periodic_state[0] = action(periodic_state[0])

        timer_ptr = [None]

        def dispose():
            self._post(DISPOSE, (timer_ptr,))

        self._post(SCHEDULE_PERIODIC, (invoke_action, timer_ptr, period))

        return CompositeDisposable(disposable, Disposable(dispose))

