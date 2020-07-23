"""
This example shows multiple on_next signatures that can be checked
with a static type checker like mypy. This example involves observables based
on two custom-made classes, A & B, where B is a subclass of A. By extension,
Iterable[B] is considered as a subtype of List[A].

Note: it is not meant to be run.
"""
from typing import List, Iterable

import rx
from rx import Observable


class A():
    ...


class B(A):
    ...


a: Observable[A] = rx.of(A(), A())
b: Observable[B] = rx.of(B(), B())

la: Observable[List[A]] = rx.of([A(), A()], [A(), A()])
lb: Observable[List[B]] = rx.of([B(), B()], [B(), B()])


def on_next_A(a: A) -> None:
    ...


def on_next_B(b: B) -> None:
    ...


def on_next_IA(ia: Iterable[A]) -> None:
    ...


def on_next_IB(ib: Iterable[B]) -> None:
    ...


# OK: we expect A and we get A
a.subscribe(on_next=on_next_A)

# KO: This should fail because we expect B here, a more specialized class of A
a.subscribe(on_next=on_next_B)

# OK: we expect B and we get B
b.subscribe(on_next=on_next_B)

# OK: we expect A and we get B, a subtype of A
b.subscribe(on_next=on_next_A)

# OK: we expect an Iterable of A and we get a List of A
la.subscribe(on_next=on_next_IA)

# KO: this should fail because we expect Iterable of B here, a more
# specialized class of List A
la.subscribe(on_next=on_next_IB)

# OK: we expect an iterable of B and we get a List of B
lb.subscribe(on_next=on_next_IB)

# OK: we expect an iterable of A and we get a more specialized List of B
lb.subscribe(on_next=on_next_IA)
