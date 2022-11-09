from multiprocessing import Process, Queue
from types import SimpleNamespace
from typing import List, Tuple

Color = SimpleNamespace(
    white=(255, 255, 255),
    black=(0, 0, 0),
    gray1=(85, 85, 85),
    gray2=(170, 170, 170),
    green=(0, 255, 0),
    red=(255, 0, 0),
)


class DecoratedString:
    def __init__(
        self,
        text: str,
        color: Tuple[int, int, int],
    ):
        self.text = text
        self.color = color

    def __eq__(self, other):

        return (
            isinstance(other, DecoratedString)
            and self.text == other.text
            and self.color == other.color
        )

    def __str__(self):

        return self.text


class AsyncFuncWrapper(Process):
    """Repeatedly run a function in a new process until receives a None input"""

    def __init__(self, func: callable, queue_in: Queue, queue_out: Queue):

        super().__init__()
        self.func = func
        self.queue_in = queue_in
        self.queue_out = queue_out
        self.daemon = True
        self.start()

    def run(self):

        inputs = self.queue_in.get()
        while inputs is not None:
            res = self.func(inputs)
            self.queue_out.put(res)
            inputs = self.queue_in.get()
            while not self.queue_in.empty() and inputs is not None:
                inputs = self.queue_in.get()
        self.queue_out.put(None)


class TaskContentBase:
    """
    Base class for tutorials & experiment where ai2thor simulator is involved
    """

    def banner(self, state) -> str:
        """A function that monitors the screen and output banner contents"""

        raise NotImplementedError

    def get_banner(self, queue_in: Queue, queue_out: Queue) -> AsyncFuncWrapper:

        return AsyncFuncWrapper(self.banner, queue_in, queue_out)

    def checklist(self, state) -> List[DecoratedString]:
        """A function that monitors the screen and output checklist contents"""

        raise NotImplementedError

    def get_checklist(self, queue_in: Queue, queue_out: Queue) -> AsyncFuncWrapper:

        return AsyncFuncWrapper(self.checklist, queue_in, queue_out)

    @property
    def ai2thor_floor_plan(self) -> str:
        """Returns the floor plan used"""

        return NotImplementedError

    def ai2thor_init_steps(self) -> List[dict]:
        """Returns actions of initialization"""

        raise NotImplementedError
