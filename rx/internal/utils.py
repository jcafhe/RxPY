from typing import Any, Iterable

from rx.disposable import CompositeDisposable


def add_ref(xs, r):
    from rx.internal import Observable

    def subscribe(observer, scheduler=None):
        return CompositeDisposable(r.disposable, xs.subscribe(observer))

    return Observable(subscribe)


def is_future(fut: Any) -> bool:
    return callable(getattr(fut, "add_done_callback", None))


def infinite() -> Iterable[int]:
    n = 0
    while True:
        yield n
        n += 1


class NotSet:
    """Sentinel value."""

    def __repr__(self):
        return 'NotSet'
