from typing import List, Iterable, Callable, TypeVar

import rx
from rx import Observable

T1 = TypeVar('T1')
T2 = TypeVar('T2')


def operator(fun: Callable[[T1], T2])-> Callable[[Observable[T1]], Observable[T2]]:
    def inner(o: Observable[T1]) ->  Observable[T2]:
        r:  Observable[T2] = Observable()
        return r
    return inner


class A():
    ...

class AA(A):
    ...


class B():
    ...


class BB(B):
    ...


class C():
    ...


class D():
    ...


class E(D):
    ...


def a_aa(x: A) -> AA:
    return AA()


def a_bb(x: A) -> BB:
    return BB()


def a_c(x: A) -> C:
    return C()

def b_c(x: B) -> C:
    return C()

def c_d(x: C)-> D:
    return D()

def d_a(x: D) -> A:
    return A()

a: Observable[A] = Observable()


# OK
a.pipe(
    operator(a_c),
    operator(c_d),
    )

# Ok: working with subtypes
a.pipe(
    operator(a_aa),
    operator(a_bb),
    operator(b_c),
    )

# KO
a.pipe(
    operator(a_c),
    operator(d_a),
    )
