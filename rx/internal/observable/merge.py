
import rx
from rx import operators as ops
from rx.internal import Observable


def _merge(*sources: Observable) -> Observable:
    return rx.from_iterable(sources).pipe(ops.merge_all())
