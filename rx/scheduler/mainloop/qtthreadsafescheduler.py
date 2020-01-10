import logging
from typing import Optional

from rx.core import typing
from rx.disposable import CompositeDisposable, Disposable, SingleAssignmentDisposable
from ..periodicscheduler import PeriodicScheduler

log = logging.getLogger(__name__)

"""
The scheduler posts custom events (RxEvent) to a handler (RxHandler) which
lives on the same qthread as the QApplication or QCoreApplication. RxEvents
are posted using the postEvent mechanism (thread-safe). These events hold
timing informations and the action function to be invoked.

Custom Qt classes (RxEvent & RxHandler) are defined at runtime to avoid import
issues.

Limitations:
    Disposables can't be disposed after the qt main loop exit (i.e. return
    of app.exec_()).

"""

SCHEDULE = 'I'           # args: (invoke_action,)
SCHEDULE_RELATIVE = 'R'  # args; (invoke_action, duetime_ms)
SCHEDULE_PERIODIC = 'P'  # args; (invoke_action, timer_ptr, period_ms)
DISPOSE = 'D'            # args: (timer_ptr,)


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
        Handles rx events posted on the qt application main loop via the
        post static method of QApplication and set/start/stop QTimers in the
        main thread.
        """

        def __init__(self, parent):
            QtCore.QObject.__init__(self, parent)

            def schedule(args):
                invoke_action = args[0]
                invoke_action()

            def schedule_relative(args):
                invoke_action, duetime_ms = args
                QtCore.QTimer.singleShot(duetime_ms, invoke_action)

            def schedule_periodic(args):
                invoke_action, timer_ptr, period_ms = args
                qtimer = QtCore.QTimer()
                qtimer.setSingleShot(False)
                qtimer.setInterval(period_ms)
                qtimer.timeout.connect(invoke_action)
                timer_ptr[0] = qtimer
                qtimer.start()

            def dispose(args):
                timer_ptr = args[0]
                try:
                    timer_ptr[0].stop()
                except AttributeError:
                    log.warning('dispose skipped for timer_ptr:{}'.format(timer_ptr))

            self.dispatcher = {
                    SCHEDULE: schedule,
                    SCHEDULE_RELATIVE: schedule_relative,
                    SCHEDULE_PERIODIC: schedule_periodic,
                    DISPOSE: dispose,
                    }

        def event(self, event):
            scheduling = event.scheduling
            args = event.args
            self.dispatcher[scheduling](args)
            return True

    return RxHandler


def create_post_function(QtCore):
    """A scheduler for a PyQt4/PyQt5/PySide event loop."""

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

    # create Handler
    current_handler = Handler(None)
    log.info('Rx Handler successfully created.')

    def post_function(scheduling, args):
        QtCore.QCoreApplication.postEvent(
                 current_handler,
                 RxEvent(scheduling, args),
                 )

    return post_function


class QtThreadSafeScheduler(PeriodicScheduler):
    """A scheduler for a PyQt4/PyQt5/PySide event loop."""
    _post = None

    def __init__(self, QtCore):
        if self._post is None:
            self._post = create_post_function(QtCore)

    def schedule(self,
                 action: typing.ScheduledAction,
                 state: Optional[typing.TState] = None
                 ) -> typing.Disposable:
        """Schedules an action to be executed.

        Args:
            action: Action to be executed.
            state: [Optional] state to be given to the action function.

        Returns:
            The disposable object used to cancel the scheduled action
            (best effort).
        """
        disposable = SingleAssignmentDisposable()
        is_disposed = False

        def invoke_action():
            if not is_disposed:
                disposable.disposable = self.invoke_action(action, state)

        def dispose():
            nonlocal is_disposed
            is_disposed = False

        self._post(SCHEDULE, (invoke_action,))
        return CompositeDisposable(disposable, Disposable(dispose))

    def schedule_relative(self,
                          duetime: typing.RelativeTime,
                          action: typing.ScheduledAction,
                          state: Optional[typing.TState] = None
                          ) -> typing.Disposable:
        """Schedules an action to be executed after duetime.

        Args:
            duetime: Relative time after which to execute the action.
            action: Action to be executed.
            state: [Optional] state to be given to the action function.

        Returns:
            The disposable object used to cancel the scheduled action
            (best effort).
        """
        duetime_ms = max(0, int(self.to_seconds(duetime) * 1000.0))
        is_disposed = False

        if duetime == 0:
            return self.schedule(action, state)

        disposable = SingleAssignmentDisposable()

        def invoke_action():
            if not is_disposed:
                disposable.disposable = self.invoke_action(action, state)

        def dispose():
            nonlocal is_disposed
            is_disposed = True

        self._post(SCHEDULE_RELATIVE, (invoke_action, duetime_ms))
        return CompositeDisposable(disposable, Disposable(dispose))

    def schedule_absolute(self,
                          duetime: typing.AbsoluteTime,
                          action: typing.ScheduledAction,
                          state: Optional[typing.TState] = None
                          ) -> typing.Disposable:
        """Schedules an action to be executed at duetime.

        Args:
            duetime: Absolute time at which to execute the action.
            action: Action to be executed.
            state: [Optional] state to be given to the action function.

        Returns:
            The disposable object used to cancel the scheduled action
            (best effort).
        """
        delta = self.to_datetime(duetime) - self.now
        return self.schedule_relative(delta, action, state=state)

    def schedule_periodic(self,
                          period: typing.RelativeTime,
                          action: typing.ScheduledPeriodicAction,
                          state: Optional[typing.TState] = None
                          ) -> typing.Disposable:
        """Schedules a periodic piece of work to be executed in the loop.

       Args:
            period: Period in seconds for running the work repeatedly.
            action: Action to be executed.
            state: [Optional] state to be given to the action function.

        Returns:
            The disposable object used to cancel the scheduled action
            (best effort).
        """
        period_ms = int(period * 1000.0)
        disposable = SingleAssignmentDisposable()
        periodic_state = state
        timer_ptr = [None]

        def invoke_action():
            nonlocal periodic_state
            periodic_state = action(periodic_state)

        def dispose():
            self._post(DISPOSE, (timer_ptr,))

        self._post(SCHEDULE_PERIODIC, (invoke_action, timer_ptr, period_ms))
        return CompositeDisposable(disposable, Disposable(dispose))
