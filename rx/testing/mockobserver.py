from typing import Any, List

from rx.internal.typing import Observer
from rx.internal.notification import OnNext, OnError, OnCompleted

from .recorded import Recorded


class MockObserver(Observer):

    def __init__(self, scheduler) -> None:
        self.scheduler = scheduler
        self.messages: List[Recorded] = []

    def on_next(self, value: Any) -> None:
        self.messages.append(Recorded(self.scheduler.clock, OnNext(value)))

    def on_error(self, error: Exception) -> None:
        self.messages.append(Recorded(self.scheduler.clock, OnError(error)))

    def on_completed(self) -> None:
        self.messages.append(Recorded(self.scheduler.clock, OnCompleted()))
