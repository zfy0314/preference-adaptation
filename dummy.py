import random

from utils import Color, DecoratedString, TaskContentBase


class Dummy(TaskContentBase):
    def banner(self, state):

        fib = lambda x: x if x < 2 else fib(x - 1) + fib(x - 2)
        _ = fib(random.randint(30, 40))  # mimic computation heavy step
        actions = [
            "Get Mug",
            "Get Lettuce",
            "Get Bread",
            "Get Plate",
            "Get Knife",
            "Cut Lettuce",
            "Cut Bread",
            "Make Coffee",
        ]
        return "Recommended Action: {}".format(random.choice(actions))

    def checklist(self, state):

        return [
            DecoratedString("Make coffee", Color.black),
            DecoratedString("  Place mug in coffee maker", Color.black),
            DecoratedString("Make sandwich", Color.black),
            DecoratedString("  Cut the bread & lettuce & tomota", Color.black),
            DecoratedString("  Assemble the sandich", Color.black),
        ]

    @property
    def ai2thor_floor_plan(self):

        return "FloorPlan10"

    @property
    def ai2thor_init_steps(self):

        return []
