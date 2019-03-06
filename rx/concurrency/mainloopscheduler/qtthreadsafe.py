import logging

from rx.core import typing
from rx.core.typing import AbsoluteTime, RelativeTime, TState, ScheduledAction, ScheduledPeriodicAction
from rx.disposable import Disposable, SingleAssignmentDisposable, CompositeDisposable
from rx.concurrency.schedulerbase import SchedulerBase

log = logging.getLogger(__name__)

"""
The scheduler posts custom events (RxEvent) to a single handler (RxHandler).
RxEvents are posted using the postEvent mechanism (thread-safe).
These events hold timing informations and function to be invoked.

Custom Qt classes (RxEvent & RxHandler) are defined at runtime to avoid import
issues.

Limitations:
    Disposables can't be disposed after the Qt event loop exits (i.e. return
    of app.exec_()).

"""

glob_post_function = None

SCHEDULE = 'Rx.SCHEDULE'                    # args: (invoke_action,)
SCHEDULE_RELATIVE = 'Rx.SCHEDULE_RELATIVE'  # args; (invoke_action, duetime)
SCHEDULE_PERIODIC = 'Rx.SCHEDULE_PERIODIC'  # args; (invoke_action, timer_ptr, period)
DISPOSE_PERIODIC = 'Rx.DISPOSE_PERIODIC'    # args: (timer_ptr,)


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
        Handles rx events posted on Qt event loop and
        invokes actions at duetime in the main thread.
        """

        def __init__(self, parent=None):
            QtCore.QObject.__init__(self, parent)
            self._periodic_timers = set()

            def schedule(invoke_action):
                # no timer needed: message already passed thru qt event loop
                invoke_action()

            def schedule_relative(invoke_action, duetime):
                QtCore.QTimer.singleShot(duetime, invoke_action)

            def schedule_periodic(invoke_action, timer_ptr, period):
                qtimer = QtCore.QTimer()
                qtimer.setSingleShot(False)
                qtimer.setInterval(period)
                qtimer.timeout.connect(invoke_action)
                timer_ptr[0] = qtimer
                self._periodic_timers.add(qtimer)
                qtimer.start()

            def dispose_periodic(timer_ptr):
                try:
                    self._periodic_timers.remove(timer_ptr[0])
                    timer_ptr[0].stop()
                    timer_ptr[0].deleteLater()
                    log.debug('delete timer_ptr:{}'.format(timer_ptr))
                except KeyError:
                    log.warning('dispose skipped for timer_ptr:{}'.format(timer_ptr))

            self.dispatcher = {
                    SCHEDULE: schedule,
                    SCHEDULE_RELATIVE: schedule_relative,
                    SCHEDULE_PERIODIC: schedule_periodic,
                    DISPOSE_PERIODIC: dispose_periodic,
                    }

        def event(self, event):
            scheduling = event.scheduling
            args = event.args

            self.dispatcher[scheduling](*args)
            return True

    return RxHandler


def QtScheduler(QtCore):
    """A scheduler for a PyQt4/PyQt5/PySide event loop."""
    global glob_post_function

    if glob_post_function is None:

        # create Handler & RxEvent classes
        qevent_type = QtCore.QEvent.registerEventType()
        RxEvent = create_RxEvent_class(QtCore, qevent_type)
        Handler = create_RxHandler_class(QtCore)
        log.info('QEvent type [{}] reserved for Rx.'.format(qevent_type))

        current_handler = Handler(None)
        log.info('Rx Handler successfully created.')

        def post_function(scheduling, *args):
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

    def schedule(self, action: ScheduledAction, state: TState = None):
        """Schedules an action to be executed."""
        sad = SingleAssignmentDisposable()
        is_disposed = False
        scheduler = self

        def invoke_action():
            if not is_disposed:
                sad.disposable = action(scheduler, state)

        def dispose():
            nonlocal is_disposed
            is_disposed = True

        self._post(SCHEDULE, invoke_action)

        return CompositeDisposable(sad, Disposable(dispose))

    def schedule_relative(self, duetime: RelativeTime, action: ScheduledAction,
                          state: TState = None):
        """Schedules an action to be executed after duetime.
        """

        duetime = int(self.to_seconds(duetime) * 1000.0)

        if duetime <= 0:
            return self.schedule(action, state)

        scheduler = self
        is_disposed = False
        sad = SingleAssignmentDisposable()

        def invoke_action():
            if not is_disposed:
                sad.disposable = action(scheduler, state)

        def dispose():
            nonlocal is_disposed
            is_disposed = True

        self._post(SCHEDULE_RELATIVE, invoke_action, duetime)

        return CompositeDisposable(sad, Disposable(dispose))

    def schedule_absolute(self, duetime: AbsoluteTime, action: ScheduledAction,
                          state: TState = None) -> typing.Disposable:
        """Schedules an action to be executed at duetime.
        """

        duetime = self.to_datetime(duetime) - self.now
        return self.schedule_relative(duetime, action, state)

    def schedule_periodic(self, period: RelativeTime, action: ScheduledPeriodicAction,
                          state: TState = None) -> typing.Disposable:
        """Schedules a periodic piece of work to be executed in the Qt
        mainloop.
        """

        period = int(self.to_seconds(period)*1000.0)
        sad = SingleAssignmentDisposable()
        timer_ptr = [None]
        periodic_state = state

        def invoke_action():
            nonlocal periodic_state
            periodic_state = action(periodic_state)

        def dispose():
            self._post(DISPOSE_PERIODIC, timer_ptr)

        self._post(SCHEDULE_PERIODIC, invoke_action, timer_ptr, period)

        return CompositeDisposable(sad, Disposable(dispose))
