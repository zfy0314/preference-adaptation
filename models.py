from time import sleep

from checklist import Checklist, SandwichChecklist
from utils import floorplans_config


class ActionSequenceModel:
    def __init__(self, floor_plan: str):
        self.checklist = SandwichChecklist()
        self.floor_plan_config = floorplans_config.get(floor_plan, {})
        self.current_step = 0
        self.total_steps = len(self.checkpoints)

    def get_config(self, key: str, default=None):
        return self.floor_plan_config.get(key, default)

    @property
    def checkpoints(self) -> list[callable]:
        raise NotImplementedError

    @property
    def instructions(self) -> list[callable]:
        raise NotImplementedError

    def __call__(self, state) -> str:

        self.checklist(state)
        while self.current_step < self.total_steps and self.checkpoints[
            self.current_step
        ](state):
            self.current_step += 1
        if self.current_step == self.total_steps:
            sleep(1.5)
            return None
        else:
            return self.instructions[self.current_step]()

    @property
    def coffee_checkpoints(self) -> list[callable]:
        return [
            lambda state: self.checklist.tasks.get_mug,
            lambda state: Checklist.is_near(
                Checklist.get_position(state, "Agent"),
                Checklist.get_position(state, "CoffeeMachine"),
                0.85,
            ),
            lambda state: self.checklist.tasks.turn_on_coffee_machine,
            lambda state: any(
                not x["isToggled"]
                for x in state.metadata["objects"]
                if x["objectType"] == "CoffeeMachine"
            ),
            lambda state: self.checklist.tasks.get_coffee,
            lambda state: self.checklist.tasks.bring_coffee,
        ]

    @property
    def coffee_instructions(self) -> list[callable]:
        return [
            lambda: "Get mug {}".format(self.get_config("mug_location", "")),
            lambda: "Walk to coffee machine",
            lambda: "Put mug in coffee machine and start brewing",
            lambda: "Wait for the coffee to brew",
            lambda: "Pick up the mug with coffee",
            lambda: "Bring coffee to the table near {}".format(
                self.get_config("chair_type", "chair")
            ),
        ]

    @property
    def sandwich_checkpoints(self) -> list[callable]:
        return [
            lambda state: self.checklist.tasks.get_plate,
            lambda state: (
                self.checklist.tasks.get_bread
                or self.checklist.tasks.get_lettuce
                or self.checklist.tasks.get_tomato
            ),
            lambda state: (
                (self.checklist.tasks.get_bread and self.checklist.tasks.get_lettuce)
                or (self.checklist.tasks.get_bread and self.checklist.tasks.get_tomato)
                or (
                    self.checklist.tasks.get_lettuce and self.checklist.tasks.get_tomato
                )
            ),
            lambda state: (
                self.checklist.tasks.get_bread
                and self.checklist.tasks.get_lettuce
                and self.checklist.tasks.get_tomato
            ),
            lambda state: self.checklist.tasks.get_knife,
            lambda state: all(
                x["parentReceptacles"] is None
                or all("Plate" not in parent for parent in x["parentReceptacles"])
                for x in state.metadata["objects"]
            ),
            lambda state: (
                self.checklist.tasks.cut_bread
                or self.checklist.tasks.cut_lettuce
                or self.checklist.tasks.cut_tomato
            ),
            lambda state: (
                (self.checklist.tasks.cut_bread and self.checklist.tasks.cut_lettuce)
                or (self.checklist.tasks.cut_bread and self.checklist.tasks.cut_tomato)
                or (
                    self.checklist.tasks.cut_lettuce and self.checklist.tasks.cut_tomato
                )
            ),
            lambda state: (
                self.checklist.tasks.cut_bread
                and self.checklist.tasks.cut_lettuce
                and self.checklist.tasks.cut_tomato
            ),
            lambda state: all(
                x["parentReceptacles"] is None
                or all("Plate" not in parent for parent in x["parentReceptacles"])
                for x in state.metadata["objects"]
            ),
            lambda state: self.checklist.tasks.place_first_bread,
            lambda state: (
                self.checklist.tasks.place_lettuce or self.checklist.tasks.place_tomato
            ),
            lambda state: (
                self.checklist.tasks.place_lettuce and self.checklist.tasks.place_tomato
            ),
            lambda state: self.checklist.tasks.place_second_bread,
            lambda state: self.checklist.tasks.bring_plate,
        ]

    @property
    def sandwich_instructions(self) -> list[callable]:
        return [
            lambda: "Get plate {}".format(self.get_config("plate_location", "")),
            lambda: "Get bread / lettuce / tomato",
            lambda: "Get bread / lettuce"
            if self.checklist.tasks.get_tomato
            else (
                "Get bread / tomato"
                if self.checklist.tasks.get_lettuce
                else "Get lettuce / tomato"
            ),
            lambda: ("Get lettuce" if self.checklist.tasks.get_tomato else "Get_tomato")
            if self.checklist.tasks.get_bread
            else "Get bread",
            lambda: "Get knife {}".format(self.get_config("knife_location", "")),
            lambda: "Empty plate",
            lambda: "Cut bread / lettuce / tomato",
            lambda: "Cut bread / lettuce"
            if self.checklist.tasks.cut_tomato
            else (
                "Cut bread / tomato"
                if self.checklist.tasks.cut_lettuce
                else "Cut lettuce / tomato"
            ),
            lambda: ("Cut lettuce" if self.checklist.tasks.cut_tomato else "Cut tomato")
            if self.checklist.tasks.cut_bread
            else "Cut bread",
            lambda: "Empty plate",
            lambda: "Pickup a slice of bread and put it on plate",
            lambda: "Pickup lettuce or tomato slice and put it on bread",
            lambda: "Pickup {} slice and put it on {} slice".format(
                "lettuce" if self.checklist.tasks.place_tomato else "tomato",
                "tomato" if self.checklist.tasks.place_tomato else "lettuce",
            ),
            lambda: "Place another slice of bread on top",
            lambda: "Bring sandwich to the table near {}".format(
                self.get_config("chair_type", "chair")
            ),
        ]


class CoffeeFirstModel(ActionSequenceModel):
    @property
    def checkpoints(self) -> list[callable]:
        return self.coffee_checkpoints + self.sandwich_checkpoints

    @property
    def instructions(self) -> list[callable]:
        return self.coffee_instructions + self.sandwich_instructions


class SandwichFirstModel(ActionSequenceModel):
    @property
    def checkpoints(self) -> list[callable]:
        return self.sandwich_checkpoints + self.coffee_checkpoints

    @property
    def instructions(self) -> list[callable]:
        return self.sandwich_instructions + self.coffee_instructions


class GreedyModel:
    def __init__(self, floor_plan: str):
        self.checklist = SandwichChecklist()
        self.floor_plan_config = floorplans_config.get(floor_plan, {})

    def __call__(self, state: dict) -> str:
        raise NotImplementedError


class MinDistanceModel:
    def __init__(self, floor_plan: str):
        self.checklist = SandwichChecklist()
        self.floor_plan_config = floorplans_config.get(floor_plan, {})

    def __call__(self, state: dict) -> str:
        raise NotImplementedError


models = {
    "greedy": GreedyModel,
    "min_distance": MinDistanceModel,
    "empty": lambda floor_plan: lambda state: "",
    "coffee_first": CoffeeFirstModel,
    "sandwich_first": SandwichFirstModel,
}


def get_model(floor_plan: str, strategy: str):
    return models[strategy](floor_plan)
