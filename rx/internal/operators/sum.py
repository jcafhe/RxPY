from typing import Callable

from rx import operators as ops
from rx.internal import Observable, pipe
from rx.internal.typing import Mapper


def _sum(key_mapper: Mapper = None) -> Callable[[Observable], Observable]:
    if key_mapper:
        return pipe(
            ops.map(key_mapper),
            ops.sum()
        )

    return ops.reduce(seed=0, accumulator=lambda prev, curr: prev + curr)
