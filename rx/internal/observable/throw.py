from typing import Any

from rx.internal import typing
from rx.internal import Observable

from rx.concurrency import immediate_scheduler


def _throw(exception: Exception, scheduler: typing.Scheduler = None) -> Observable:
    exception = exception if isinstance(exception, Exception) else Exception(exception)

    def subscribe(observer: typing.Observer, scheduler: typing.Scheduler = None) -> typing.Disposable:
        _scheduler = scheduler or immediate_scheduler

        def action(scheduler: typing.Scheduler, state: Any):
            observer.on_error(exception)

        return _scheduler.schedule(action)
    return Observable(subscribe)
