import json
from collections import namedtuple
from multiprocessing import Process, Queue
from time import time
from types import SimpleNamespace
from typing import Tuple

Color = SimpleNamespace(
    white=(255, 255, 255),
    black=(0, 0, 0),
    gray1=(85, 85, 85),
    gray2=(170, 170, 170),
    green=(0, 255, 0),
    red=(255, 0, 0),
)


class Logger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.actions = {}
        self.surveys = {}

    def log_action(self, task: str, action: dict):
        try:
            self.actions[task].append((time(), action))
        except KeyError:
            self.actions[task] = [(time(), action)]

    def log_survey(self, survey: str, res: int):
        self.surveys[survey] = (time(), res)

    def save(self):
        json.dump(
            dict(actions=self.actions, surveys=self.surveys),
            open(self.log_file, "w"),
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
        res = True
        while inputs is not None and res is not None:
            res = self.func(inputs)
            self.queue_out.put(res)
            inputs = self.queue_in.get()
            while not self.queue_in.empty() and inputs is not None:
                inputs = self.queue_in.get()
        print("Got None, exiting")
        self.queue_out.put(None)


Task = namedtuple(
    "Task",
    [
        "name",
        "banner_func",
        "checklist_func",
        "floor_plan",
        "init_steps",
        "instructions",
    ],
)
Survey = namedtuple("Survey", ["name", "question"])
