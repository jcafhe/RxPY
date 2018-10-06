import logging

from rx.core import Disposable
from rx.disposables import SingleAssignmentDisposable, CompositeDisposable
from rx.concurrency.schedulerbase import SchedulerBase

log = logging.getLogger("Rx")

"""

The trick is to defered the Qtimer start/stop actions to the qapplication
thread using the postEvent mechanism (thread-safe).

The scheduler posts custom events (RxEvent) with timing informations and
interval function to the qapplication which lives on the main thread.
These events are processed by a handler attached to the qapplication. It
constructs, starts, stops QTimer and connect timeout signal to the
corresponding interval function. Qtimers are dispatched by their timing
parameters which define their identities.

Custom Qt classes (RxEvent & Handler) are defined on runtime to avoid import
issues.
"""

HANDLER_NAME = 'Rx.EVENTHANDLER'
SCHEDULE = 'Rx.SCHEDULE'
DISPOSE = 'Rx.DISPOSE'


def create_Handler_class(QtCore, qevent_type):
    """
    Creates an Handler class that interacts only with a QEvent of a certain
    type.
    """

    class RxEvent(QtCore.QEvent):
        """
        Custom QEvent that holds QTimer parameters to be used by Handler to
        start/stop QTimer on the qapplication thread.
        """
        def __init__(self, timer_action, args):
            QtCore.QEvent.__init__(self, qevent_type)
            self.args = args      # (interval, periodic, msecs)
            self.timer_action = timer_action  # 'schedule' or 'dispose'

    # hack to set a class member with the same name
    RxEvent_ = RxEvent

    class Handler(QtCore.QObject):
        """
        Handles rx events posted on the qt application main loop and
        triggers QTimers in the main thread.

        Handler object is set as a child of the qt application and installed
        as an event filter.
        """

        RxEvent = RxEvent_

        def __init__(self, qapplication):
            QtCore.QObject.__init__(self, qapplication)
            qapplication.installEventFilter(self)
            self._timers_by_args = {}

        def eventFilter(self, watcher, event):
            if event.type() != qevent_type:
                return False

            timer_action = event.timer_action
            args = event.args

            if timer_action == SCHEDULE:
                interval, periodic, msecs = args
                timer = QtCore.QTimer()
                timer.setSingleShot(not periodic)
                timer.setInterval(msecs)
                timer.timeout.connect(interval)
                self._timers_by_args[args] = timer
                timer.start()
            else:
                timer = self._timers_by_args[args]
                timer.stop()
                self._timers_by_args.pop(args)

            return True

    return Handler


def QtScheduler(QtCore):
    """A scheduler for a PyQt4/PyQt5/PySide event loop."""

    # Get the current QApplication running
    qapp = QtCore.QCoreApplication.instance()
    if qapp is None:
        raise RuntimeError(
                "Unable to get instance of QCoreAplication. "
                "A QCoreApplication must be instanciate before creating a "
                "rx QtScheduler (e.g. qapp = QtWidgets.QApplication([])."
                )

    # try to get the handler attached to qapp or construct one
    current_handler = qapp.findChild(QtCore.QObject, HANDLER_NAME)

    if current_handler is None:
        qevent_type = QtCore.QEvent.registerEventType()
        Handler = create_Handler_class(QtCore, qevent_type)
        current_handler = Handler(qapp)
        current_handler.setObjectName(HANDLER_NAME)
        log.info('QEvent type [{}] reserved for Rx.'.format(qevent_type))
        log.info('Rx Handler successfully attached to qapplication.')

    RxEvent = current_handler.RxEvent

    def post_function(timer_action, args):
        QtCore.QCoreApplication.postEvent(
                 current_handler,
                 RxEvent(timer_action, args),
                 )

    return _QtScheduler(post_function)


class _QtScheduler(SchedulerBase):
    """A scheduler for a PyQt4/PyQt5/PySide event loop."""

    def __init__(self, post_function):
        self._post = post_function

    def _qtimer_schedule(self, time, action, state, periodic=False):
        scheduler = self
        msecs = self.to_relative(time)

        disposable = SingleAssignmentDisposable()

        periodic_state = [state]

        def interval():
            if periodic:
                periodic_state[0] = action(periodic_state[0])
            else:
                disposable.disposable = action(scheduler, state)

        log.debug("QtScheduler timeout: %s", msecs)

        args = (interval, periodic, msecs)
        self._post(SCHEDULE, args)

        def dispose():
            self._post(DISPOSE, args)

        return CompositeDisposable(disposable, Disposable.create(dispose))

    def schedule(self, action, state=None):
        """Schedules an action to be executed."""
        return self._qtimer_schedule(0, action, state)

    def schedule_relative(self, duetime, action, state=None):
        """Schedules an action to be executed after duetime.

        Keyword arguments:
        duetime -- {timedelta} Relative time after which to execute the action.
        action -- {Function} Action to be executed.

        Returns {Disposable} The disposable object used to cancel the scheduled
        action (best effort)."""
        return self._qtimer_schedule(duetime, action, state)

    def schedule_absolute(self, duetime, action, state=None):
        """Schedules an action to be executed at duetime.

        Keyword arguments:
        duetime -- {datetime} Absolute time after which to execute the action.
        action -- {Function} Action to be executed.

        Returns {Disposable} The disposable object used to cancel the scheduled
        action (best effort)."""

        duetime = self.to_datetime(duetime)
        return self._qtimer_schedule(duetime, action, state)

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

        return self._qtimer_schedule(period, action, state, periodic=True)
