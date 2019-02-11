from rx import timer
from rx.internal import Observable, typing


def _interval(period, scheduler: typing.Scheduler = None) -> Observable:
    return timer(period, period, scheduler)
