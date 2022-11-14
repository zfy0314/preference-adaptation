import json
from types import SimpleNamespace
from typing import List, Tuple

from utils import Color, DecoratedString


class Checklist:
    @staticmethod
    def is_picked_up(state, object_type: str) -> bool:
        return any(
            x["parentReceptacles"] is None
            for x in state.metadata["objects"]
            if x["objectType"] == object_type
        )

    @staticmethod
    def is_put_down(state, object_type: str) -> bool:
        return all(
            x["parentReceptacles"] is not None
            for x in state.metadata["objects"]
            if x["objectType"] == object_type
        )

    @staticmethod
    def is_put_on(state, object_type: str, surface_type: str) -> bool:
        return any(
            x["parentReceptacles"] is not None
            and any(surface_type in parent for parent in x["parentReceptacles"])
            for x in state.metadata["objects"]
            if x["objectType"] == object_type
        )

    @staticmethod
    def is_open(state, object_type: str) -> bool:
        return any(
            x["isOpen"]
            for x in state.metadata["objects"]
            if x["objectType"] == object_type
        )

    @staticmethod
    def is_close(state, object_type: str) -> bool:
        return all(
            not x["isOpen"]
            for x in state.metadata["objects"]
            if x["objectType"] == object_type
        )

    @staticmethod
    def exists(state, object_type: str) -> bool:
        return any(x["objectType"] == object_type for x in state.metadata["objects"])

    @staticmethod
    def is_near(position1: dict, position2: dict) -> bool:
        return (
            max(
                abs(position1["x"] - position2["x"]),
                abs(position1["z"] - position2["z"]),
            )
            < 0.58
        )


class SandwichChecklist:

    chair_location: Tuple[float, float]

    def __init__(self):
        self.completed = False
        self.tasks = SimpleNamespace(
            get_mug=False,
            get_bread=False,
            get_tomato=False,
            get_plate=False,
            get_knife=False,
            cut_lettuce=False,
            cut_bread=False,
            cut_tomato=False,
            place_first_bread=False,
            place_lettuce=False,
            place_tomato=False,
            place_second_bread=False,
            turn_on_coffee_machine=False,
            get_coffee=False,
            bring_coffee=False,
            bring_plate=False,
        )

    def check_get_mug(self, state) -> bool:
        return Checklist.is_picked_up(state, "Mug")

    def check_get_bread(self, state) -> bool:
        return Checklist.is_picked_up(state, "Bread") or self.tasks.cut_bread

    def check_get_lettuce(self, state) -> bool:
        return Checklist.is_picked_up(state, "Lettuce") or self.tasks.cut_lettuce

    def check_get_tomato(self, state) -> bool:
        return Checklist.is_picked_up(state, "Tomato") or self.tasks.cut_tomato

    def check_get_knife(self, state) -> bool:
        return Checklist.is_picked_up(state, "Knife")

    def check_get_plate(self, state) -> bool:
        return Checklist.is_picked_up(state, "Plate")

    def check_cut_bread(self, state) -> bool:
        return Checklist.exists(state, "BreadSliced")

    def check_cut_lettuce(self, state) -> bool:
        return Checklist.exists(state, "LettuceSliced")

    def check_cut_tomato(self, state) -> bool:
        return Checklist.exists(state, "TomatoSliced")

    def check_place_first_bread(self, state) -> bool:
        return Checklist.is_put_on(state, "BreadSliced", "Plate")

    def check_place_lettuce(self, state) -> bool:
        return Checklist.is_put_on(state, "LettuceSliced", "Plate")

    def check_place_tomato(self, state) -> bool:
        return Checklist.is_put_on(state, "TomatoSliced", "Plate")

    def check_place_second_bread(self, state) -> bool:
        return [
            x["parentReceptacles"] is not None
            and any("Plate" in parent for parent in x["parentReceptacles"])
            for x in state.metadata["objects"]
            if x["objectType"] == "BreadSliced"
        ].count(True) >= 2

    def check_turn_on_coffee_machine(self, state) -> bool:
        return any(
            x["isToggled"]
            for x in state.metadata["objects"]
            if x["objectType"] == "CoffeeMachine"
        )

    def check_get_coffee(self, state) -> bool:
        return Checklist.is_picked_up(state, "Mug") and any(
            x["isFilledWithLiquid"]
            for x in state.metadata["objects"]
            if x["objectType"] == "Mug"
        )

    def check_bring_coffee(self, state) -> bool:

        mug_position = [
            x["position"] for x in state.metadata["objects"] if x["objectType"] == "Mug"
        ][0]
        return (
            self.tasks.get_coffee
            and Checklist.is_near(self.chair_location, mug_position)
            and Checklist.is_put_down(state, "Mug")
        )

    def check_bring_plate(self, state) -> bool:

        plate_position = [
            x["position"]
            for x in state.metadata["objects"]
            if x["objectType"] == "Plate"
        ][0]
        return (
            self.tasks.get_coffee
            and Checklist.is_near(self.chair_location, plate_position)
            and Checklist.is_put_down(state, "Plate")
        )

    def __call__(self, state) -> List[DecoratedString]:

        if self.completed:
            return None

        for task, checked in self.tasks.__dict__.items():
            if not checked:
                setattr(self.tasks, task, getattr(self, "check_" + task)(state))

        completed = list(self.tasks.__dict__.values()).count(True)
        incomplete = list(self.tasks.__dict__.values()).count(False)

        if incomplete == 0:
            self.completed = True
            return [DecoratedString("All completed!", Color.green)]
        else:
            return [
                DecoratedString("{} steps completed".format(completed), Color.green),
                DecoratedString("{} steps incomplete".format(incomplete), Color.red),
            ]


def get_checklist(floor_plan: str) -> SandwichChecklist:

    config = json.load(open("floorplans.json", "r"))
    checklist_obj = SandwichChecklist()
    checklist_obj.chair_location = config[floor_plan]["chair_location"]
    return checklist_obj
