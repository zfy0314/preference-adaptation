from random import randint

from utils import Color, DecoratedString, Survey, Task

fib = lambda x: x if x < 2 else fib(x - 1) + fib(x - 2)
actions = [
    "Get Mug",
    "Get Lettuce",
    "Get Bread",
    "Get Plate",
    "Get Knife",
    "Get Tomato",
    "Cut Lettuce",
    "Cut Bread",
    "Cut Lettuce",
    "Cut Tomato",
    "Make Coffee",
    "Walk to Chair",
]

dummy_presurvey = Survey(
    name="presurvey", question="You have interacted with AI2THOR before"
)
dummy_postsurvey = Survey(name="postsurvey", question="The simulator is easy to use")

dummy_task = Task(
    name="dummy",
    banner_func=lambda _: "Recommended action: "
    + actions[fib(randint(30, 40)) % len(actions) - randint(0, len(actions))],
    checklist_func=lambda _: [
        DecoratedString("Make coffee", Color.black),
        DecoratedString("  Place mug in coffee maker", Color.black),
        DecoratedString("Make sandwich", Color.black),
        DecoratedString("  Cut the bread & lettuce & tomota", Color.black),
        DecoratedString("  Assemble the sandich", Color.black),
    ],
    floor_plan="FloorPlan10",
    init_steps=[],
    instructions=[
        "Instructions:",
        "Press [ESC] to quit",
        "Press [E] to open/close {fridge, cupboard, microwave ...}",
        "Press [F] to turn on/off {stove, microwave, coffee machine, ...}",
        "Press [Q] to drop items in hand",
        "Press [mouse] to pick up / put down / cut (with knife) objects",
    ],
)
