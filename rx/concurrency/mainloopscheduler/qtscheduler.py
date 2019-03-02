import logging

from rx.disposable import Disposable
from rx.core import typing
from rx.disposable import SingleAssignmentDisposable, CompositeDisposable
from rx.concurrency.schedulerbase import SchedulerBase

logger = logging.getLogger(__name__)


class QtScheduler(SchedulerBase):
    """A scheduler for a PyQt4/PyQt5/PySide event loop."""

    def __init__(self, qtcore):
        self.qtcore = qtcore
        self._timers = set()

    def _remove_and_stop_timer(self, qtimer):
        """
        Stop (if not already stopped), remove and delete a QTimer object.
        """
        try:
            self._timers.remove(qtimer)
            qtimer.stop()
            qtimer.deleteLater()
        except KeyError:
            pass

    def schedule(self, action: typing.ScheduledAction, state: typing.TState = None) -> typing.Disposable:
        """Schedules an action to be executed."""
        return self.schedule_relative(0.0, action, state)

    def schedule_relative(self, duetime: typing.RelativeTime, action: typing.ScheduledAction,
                          state: typing.TState = None) -> typing.Disposable:
        """Schedules an action to be executed after duetime.

        Args:
            duetime: Relative time after which to execute the action.
            action: Action to be executed.

        Returns:
            The disposable object used to cancel the scheduled action
            (best effort).
        """
        scheduler = self
        msecs = int(self.to_seconds(duetime)*1000.0)
        sad = SingleAssignmentDisposable()

        def invoke_action():
            sad.disposable = action(scheduler, state)
            self._remove_and_stop_timer(timer)

        timer = self.qtcore.QTimer()
        timer.setSingleShot(True)
        timer.setInterval(msecs)
        timer.timeout.connect(invoke_action)
        self._timers.add(timer)
        timer.start()

        def dispose():
            self._remove_and_stop_timer(timer)

        return CompositeDisposable(sad, Disposable(dispose))


    def schedule_absolute(self, duetime: typing.AbsoluteTime, action: typing.ScheduledAction,
                          state: typing.TState = None) -> typing.Disposable:
        """Schedules an action to be executed at duetime.

        Args:
            duetime: Absolute time after which to execute the action.
            action: Action to be executed.

        Returns:
            The disposable object used to cancel the scheduled action
            (best effort).
        """
        duetime = self.to_datetime(duetime) - self.now
        return self.schedule_relative(duetime, action, state)

    def schedule_periodic(self, period: typing.RelativeTime, action: typing.ScheduledPeriodicAction,
                          state: typing.TState = None):
        """Schedules a periodic piece of work to be executed in the Qt
        mainloop.

        Args:
            period: Period in milliseconds for running the work
                periodically.
            action: Action to be executed.
            state: [Optional] Initial state passed to the action upon
                the first iteration.

        Returns:
            The disposable object used to cancel the scheduled
            recurring action (best effort).
        """

        msecs = int(self.to_seconds(period)*1000.0)
        sad = SingleAssignmentDisposable()
        periodic_state = state

        def interval():
            nonlocal periodic_state
            periodic_state = action(periodic_state)

        timer = self.qtcore.QTimer()
        timer.setSingleShot(False)
        timer.setInterval(msecs)
        timer.timeout.connect(interval)
        timer.start()
        self._timers.add(timer)

        def dispose():
            self._remove_and_stop_timer(timer)

        return CompositeDisposable(sad, Disposable(dispose))
