from types import SimpleNamespace
from typing import List

from utils import Color, DecoratedString


class ChecklistBase:
    tasks: SimpleNamespace

    def __init__(self):
        self.initialized = False

    def __call__(self, state) -> List[DecoratedString]:

        if self.initialized:
            self.check_all(state)
        else:
            self.log_start_state(state)
        try:
            return getattr(self, "return_method")()
        except AttributeError:
            return self.return_count()

    def return_list(self) -> List[DecoratedString]:
        return [
            DecoratedString(task, Color.green if completion else Color.red)
            for task, completion in sorted(self.tasks.__dict__)
        ]

    def return_count(self) -> List[DecoratedString]:
        return [
            DecoratedString(
                "{} steps completed".format(self.tasks.__dict__.values().count(True)),
                Color.green,
            ),
            DecoratedString(
                "{} steps completed".format(self.tasks.__dict__.values().count(False)),
                Color.green,
            ),
        ]
