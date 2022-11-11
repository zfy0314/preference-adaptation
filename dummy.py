from random import randint

from utils import Color, DecoratedString, Survey, Task

fib = lambda x: x if x < 2 else fib(x - 1) + fib(x - 2)
actions = [
    "Get Lettuce",
    "Get Bread",
    "Get Tomato",
    "Get Mug",
    "Get Plate",
    "Get Knife",
    "Cut Lettuce",
    "Cut Bread",
    "Cut Tomato",
    "Place Lettuce on Bread" "Place Slice of Bread",
    "Place Tomato on Bread" "Bring Sandwich to Chair",
    "Walk to Coffee Machine",
    "Turn on Coffee Machine",
    "Wait for Coffee to Brew",
    "Bring Coffee to Chair",
]
# Actions for tutorial
coffee_actions = [
    "Find Mug",
    "Pickup Mug (click mouse)",
    "Put Mug in Coffee Maker (click mouse)",
    "Start Coffee Maker (press [F])",
]
delayed_pick = lambda arr: arr[fib(randint(30, 40)) % len(arr) - randint(0, len(arr))]

presurvey1 = Survey(
    name="presurvey1", question="You have interacted with AI2THOR before"
)
presurvey2 = Survey(
    name="presurvey2", question="You prepare breakfast for yourself a lot"
)
postsurvey1 = Survey(name="postsurvey1", question="The task is easy")
postsurvey2 = Survey(
    name="postsurvey2", question="The suggestions provided by the agent is helpful"
)

instructions = [
    "Instructions:",
    "Press [ESC] to quit",
    "Press [E] to open/close {fridge, cupboard, microwave ...}",
    "Press [F] to turn on/off {stove, microwave, coffee machine, ...}",
    "Press [Q] to drop items in hand",
    "Press [mouse] to pick up / put down / cut (with knife) objects",
]
tutorial = Task(
    name="tutorial",
    banner_func=lambda _: delayed_pick(coffee_actions),
    checklist_func=lambda _: [
        DecoratedString("Make coffee", Color.black),
    ],
    floor_plan="FloorPlan5",
    init_steps=[],
    instructions=[
        "Lets go through a tutorial of using the Coffee Machine",
    ],
)
train = Task(
    name="train",
    banner_func=lambda _: "",
    checklist_func=lambda _: [
        DecoratedString("Make coffee", Color.black),
        DecoratedString("  Place mug in coffee maker", Color.black),
        DecoratedString("Make sandwich", Color.black),
        DecoratedString("  Cut the bread & lettuce & tomota", Color.black),
        DecoratedString("  Assemble the sandich", Color.black),
    ],
    floor_plan="FloorPlan5",
    init_steps=[],
    instructions=[
        "Now try to make a breakfast by yourself",
    ],
)
baseline = Task(
    name="baseline",
    banner_func=lambda _: "Recommended action: " + delayed_pick(actions),
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
        "You are at a new kitchen, and a agent",
        "will assist you by providing suggestions",
    ],
)
personalized = Task(
    name="personalized",
    banner_func=lambda _: "Recommended action: " + delayed_pick(actions),
    checklist_func=lambda _: [
        DecoratedString("Make coffee", Color.black),
        DecoratedString("  Place mug in coffee maker", Color.black),
        DecoratedString("Make sandwich", Color.black),
        DecoratedString("  Cut the bread & lettuce & tomota", Color.black),
        DecoratedString("  Assemble the sandich", Color.black),
    ],
    floor_plan="FloorPlan14",
    init_steps=[],
    instructions=[
        "You are at another new kitchen, and a",
        "different agent will assist you",
        "by providing suggestions",
    ],
)

dummy_procedures = [
    presurvey1,
    presurvey2,
    instructions,
    tutorial,
    train,
    baseline,
    postsurvey1,
    postsurvey2,
    personalized,
    postsurvey1,
    postsurvey2,
]
