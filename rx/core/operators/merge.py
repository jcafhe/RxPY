from typing import Callable

import rx
from rx import from_future
from rx.core import Observable, AnonymousObservable
from rx.disposables import CompositeDisposable, SingleAssignmentDisposable
from rx.internal.concurrency import synchronized
from rx.internal.utils import is_future


def _merge(*args, max_concurrent: int = None) -> Callable[[Observable], Observable]:
    def merge(source: Observable) -> Observable:
        """Merges an observable sequence of observable sequences into
        an observable sequence, limiting the number of concurrent
        subscriptions to inner sequences. Or merges two observable
        sequences into a single observable sequence.

        Examples:
            >>> merged = merge(sources)

        Args:
            source: Source observable.

        Returns:
            The observable sequence that merges the elements of the
            inner sequences.
        """

        if max_concurrent is None:
            sources = tuple([source]) + args
            return rx.merge(*sources)

        def subscribe(observer, scheduler=None):
            active_count = [0]
            group = CompositeDisposable()
            is_stopped = [False]
            queue = []

            def subscribe(xs):
                subscription = SingleAssignmentDisposable()
                group.add(subscription)

                @synchronized(source.lock)
                def on_completed():
                    group.remove(subscription)
                    if queue:
                        s = queue.pop(0)
                        subscribe(s)
                    else:
                        active_count[0] -= 1
                        if is_stopped[0] and active_count[0] == 0:
                            observer.on_completed()

                on_next = synchronized(source.lock)(observer.on_next)
                on_error = synchronized(source.lock)(observer.on_error)
                subscription.disposable = xs.subscribe_(on_next, on_error, on_completed, scheduler)

            def on_next(inner_source):
                if active_count[0] < max_concurrent:
                    active_count[0] += 1
                    subscribe(inner_source)
                else:
                    queue.append(inner_source)

            def on_completed():
                is_stopped[0] = True
                if active_count[0] == 0:
                    observer.on_completed()

            group.add(source.subscribe_(on_next, observer.on_error, on_completed, scheduler))
            return group
        return AnonymousObservable(subscribe)
    return merge


def _merge_all() -> Callable[[Observable], Observable]:
    def merge_all(source: Observable) -> Observable:
        """Partially applied merge_all operator.

        Merges an observable sequence of observable sequences into an
        observable sequence.

        Args:
            source: Source observable to merge.

        Returns:
            The observable sequence that merges the elements of the inner
            sequences.
        """
        def subscribe(observer, scheduler=None):
            group = CompositeDisposable()
            is_stopped = [False]
            m = SingleAssignmentDisposable()
            group.add(m)

            def on_next(inner_source):
                inner_subscription = SingleAssignmentDisposable()
                group.add(inner_subscription)

                inner_source = from_future(inner_source) if is_future(inner_source) else inner_source

                @synchronized(source.lock)
                def on_completed():
                    group.remove(inner_subscription)
                    if is_stopped[0] and len(group) == 1:
                        observer.on_completed()

                on_next = synchronized(source.lock)(observer.on_next)
                on_error = synchronized(source.lock)(observer.on_error)
                disposable = inner_source.subscribe_(on_next, on_error, on_completed, scheduler)
                inner_subscription.disposable = disposable

            def on_completed():
                is_stopped[0] = True
                if len(group) == 1:
                    observer.on_completed()

            m.disposable = source.subscribe_(on_next, observer.on_error, on_completed, scheduler)
            return group

        return AnonymousObservable(subscribe)
    return merge_all
