"""
This file is current a mess, will clean up later
"""

import json
import os
from collections import UserList, namedtuple
from datetime import datetime, timedelta
from functools import cache, cached_property
from glob import glob
from itertools import permutations, product
from pprint import pprint
from typing import List, Tuple

import ai2thor.controller
import cv2
import fire
from ai2thor.platform import CloudRendering
from matplotlib import pyplot as plt
from scipy.stats import ttest_ind
from tqdm import tqdm

from checklist import SandwichChecklist


class PartiallyOrderedList(UserList):
    @cached_property
    def all_orderings(self) -> List[Tuple[str]]:
        lists = [[]]
        for item in self.data:
            if isinstance(item, set):
                lists = [x + list(y) for x, y in product(lists, permutations(item))]
            else:
                for x in lists:
                    x.append(item)
        return [tuple(x) for x in lists]

    @staticmethod
    @cache
    def _edit_distance(
        seq: tuple, template: tuple, seq_start: int, template_start: int
    ) -> int:
        if seq_start >= len(seq):
            res = len(template) - template_start
        elif template_start >= len(template):
            res = len(seq) - seq_start
        elif seq[seq_start] == template[template_start]:
            res = PartiallyOrderedList._edit_distance(
                seq, template, seq_start + 1, template_start + 1
            )
        else:
            res = 1 + min(
                PartiallyOrderedList._edit_distance(
                    seq, template, seq_start + 1, template_start + 1
                ),
                PartiallyOrderedList._edit_distance(
                    seq, template, seq_start, template_start + 1
                ),
                PartiallyOrderedList._edit_distance(
                    seq, template, seq_start + 1, template_start
                ),
            )
        return res

    def edit_distance(self, seq: list) -> int:
        return min(
            self._edit_distance(tuple(seq), temp, 0, 0) for temp in self.all_orderings
        )


default_sequences = dict(
    coffee_first=PartiallyOrderedList(
        [
            "get_mug",
            "turn_on_coffee_machine",
            "get_coffee",
            "bring_coffee",
            "get_plate",
            {"get_bread", "get_lettuce", "get_tomato"},
            "get_knife",
            {"cut_lettuce", "cut_bread", "cut_tomato"},
            "place_first_bread",
            {"place_lettuce", "place_tomato"},
            "place_second_bread",
            "bring_plate",
        ]
    ),
    sandwich_first=PartiallyOrderedList(
        [
            "get_plate",
            {"get_bread", "get_lettuce", "get_tomato"},
            "get_knife",
            {"cut_lettuce", "cut_bread", "cut_tomato"},
            "place_first_bread",
            {"place_lettuce", "place_tomato"},
            "place_second_bread",
            "bring_plate",
            "get_mug",
            "turn_on_coffee_machine",
            "get_coffee",
            "bring_coffee",
        ]
    ),
    interleave=PartiallyOrderedList(
        [
            "get_mug",
            "turn_on_coffee_machine",
            "get_plate",
            {"get_bread", "get_lettuce", "get_tomato"},
            "get_knife",
            {"cut_lettuce", "cut_bread", "cut_tomato"},
            "place_first_bread",
            {"place_lettuce", "place_tomato"},
            "place_second_bread",
            "bring_plate",
            "get_coffee",
            "bring_coffee",
        ]
    ),
)

annotate = (
    lambda x: "***"
    if x.pvalue < 0.001
    else "**"
    if x.pvalue < 0.01
    else "*"
    if x.pvalue < 0.05
    else "n.s."
)


def parse_time(time_str: str) -> datetime:
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")


def make_video(
    actions: List[Tuple[str, dict]],
    file_name: str,
    floor_plan: str,
    frame_rate: int = 100,
    size: Tuple[int, int] = (1440, 810),
):

    writer = cv2.VideoWriter(
        file_name, cv2.VideoWriter_fourcc(*"mp4v"), frame_rate, size
    )
    controller = ai2thor.controller.Controller(
        platform=CloudRendering,
        scene=floor_plan,
        width=size[0],
        height=size[1],
        gridSize=0.05,
        snapToGrid=False,
        fieldOfView=60,
    )
    state = controller.step(action="Teleport")
    frame = state.cv2img
    writer.write(frame)
    current = parse_time(actions[0][0])
    i = 0

    with tqdm(total=len(actions)) as pbar:
        while i < len(actions):
            time, action = actions[i]
            while (parse_time(time) < current) and (i < len(actions) - 1):
                state = controller.step(**action)
                i += 1
                pbar.update(1)
                time, action = actions[i]
            if parse_time(time) - current < timedelta(seconds=1 / frame_rate):
                state = controller.step(**action)
                frame = state.cv2img
                time, action = actions[i]
                i += 1
                pbar.update(1)
            writer.write(frame)
            current += timedelta(seconds=1 / frame_rate)

    controller.step(action="Done")
    writer.release()


def make_video_from_results(
    result_file: str,
    video_file: str,
    key: str,
    frame_rate: int = 25,
    size: Tuple[int, int] = (1440, 810),
):

    if key.startswith("FloorPlan"):
        floor_plan = key.split(" ")[0]
    else:
        floor_plan = "FloorPlan5"

    result = json.load(open(result_file, "r"))

    make_video(result["actions"][key], video_file, floor_plan, frame_rate, size)


def make_all_result_videos():

    for json_file in os.listdir("results"):
        if json_file.endswith(".json"):
            data = json.load(open(os.path.join("results", json_file), "r"))["actions"]
            for key, actions in data.items():
                key = key.replace(" ", "_").replace("'", "")
                if not key.startswith("<class_tutorial") and "train" in key:
                    print(json_file, key)
                    if key.startswith("FloorPlan"):
                        floor_plan = key.split("_")[0]
                    else:
                        floor_plan = "FloorPlan5"
                    try:
                        make_video(
                            actions,
                            os.path.join(
                                "replay",
                                json_file.replace(".json", "{}.mp4".format(key)),
                            ),
                            floor_plan,
                            25,
                            (1280, 720),
                        )
                    except Exception as e:
                        print("crashed!", e)


PostTestSurvey = namedtuple(
    "PostTestSurvey", ["easy", "attention", "follow", "helpful", "reasonable"]
)
Participant = namedtuple(
    "Participant",
    ["simulator", "coffee_first", "sandwich_first", "interleave", "json_file"],
)


def parse_survey(json_file: str) -> Participant:

    result = json.load(open(json_file))
    last_timestep = [
        (parse_time(actions[-1][0]), key)
        for key, actions in result["actions"].items()
        if key.startswith("FloorPlan")
    ]
    try:
        survey_timesteps = [
            (parse_time(response[0]), i)
            for i, response in enumerate(result["surveys"]["post_test_survey_1"])
        ]
    except (ValueError, KeyError):
        print(json_file)
    ordered = sorted(last_timestep + survey_timesteps, key=lambda x: x[0])
    try:
        key2id = {
            ordered[i][1].split(" ")[-1]: ordered[i + 1][1] for i in range(0, 6, 2)
        }
    except IndexError:
        print(json_file)
        print(ordered)
    response = result["surveys"]
    return Participant(
        simulator=result["surveys"]["post_train_survey"][0][1],
        coffee_first=PostTestSurvey(
            easy=response["post_test_survey_1"][key2id["coffee_first"]][1],
            attention=response["post_test_survey_2"][key2id["coffee_first"]][1],
            helpful=response["post_test_survey_3"][key2id["coffee_first"]][1],
            reasonable=response["post_test_survey_4"][key2id["coffee_first"]][1],
            follow=response["post_test_survey_5"][key2id["coffee_first"]][1],
        ),
        sandwich_first=PostTestSurvey(
            easy=response["post_test_survey_1"][key2id["sandwich_first"]][1],
            attention=response["post_test_survey_2"][key2id["sandwich_first"]][1],
            helpful=response["post_test_survey_3"][key2id["sandwich_first"]][1],
            reasonable=response["post_test_survey_4"][key2id["sandwich_first"]][1],
            follow=response["post_test_survey_5"][key2id["sandwich_first"]][1],
        ),
        interleave=PostTestSurvey(
            easy=response["post_test_survey_1"][key2id["interleave"]][1],
            attention=response["post_test_survey_2"][key2id["interleave"]][1],
            helpful=response["post_test_survey_3"][key2id["interleave"]][1],
            reasonable=response["post_test_survey_4"][key2id["interleave"]][1],
            follow=response["post_test_survey_5"][key2id["interleave"]][1],
        ),
        json_file=json_file,
    )


def parse_all_surveys() -> List[Participant]:
    return [parse_survey(json_file) for json_file in glob("results/*.json")]


def draw_time(png_file: str):

    plt.rcParams.update({"font.size": 14})
    matching = json.load(open("matching.json"))
    lengths = {
        "sandwich_first": [],
        "coffee_first": [],
        "interleave": [],
        "personalized": [],
    }
    for json_file in glob("results/*.json"):
        action_logs = json.load(open(json_file, "r"))["actions"]
        for key, actions in action_logs.items():
            if key.split(" ")[-1] in lengths.keys():
                mode = key.split(" ")[-1]
                interval = (
                    parse_time(actions[-1][0]) - parse_time(actions[0][0])
                ).total_seconds()
                lengths[mode].append(interval)
                if matching[json_file][1] == mode:
                    lengths["personalized"].append(interval)
    boxplot = plt.boxplot(
        [
            lengths["coffee_first"],
            lengths["sandwich_first"],
            lengths["interleave"],
            lengths["personalized"],
        ],
        widths=0.8,
        patch_artist=True,
    )
    for i, name in enumerate(["coffee_first", "sandwich_first", "interleave"]):
        plt.plot(
            [i + 1, i + 1, 4, 4],
            [215 + 15 * i, 217 + 15 * i, 217 + 15 * i, 215 + 15 * i],
            color="black",
        )
        plt.text(
            2.25 + i / 2,
            220 + 15 * i,
            annotate(ttest_ind(lengths[name], lengths["personalized"])),
        )
    for patch, color in zip(
        boxplot["boxes"], ["pink", "lightblue", "lightgreen", "orchid"]
    ):
        patch.set_facecolor(color)
    plt.legend(
        boxplot["boxes"],
        ["coffee first", "sandwich first", "interleave", "personalized"],
    )
    plt.xlim(0, 8)
    plt.ylim(60, 270)
    plt.xticks([])
    plt.ylabel("time taken (s)")
    plt.xlabel("different agents")
    plt.tight_layout()
    plt.savefig(png_file)


def draw_distance(png_file: str):

    plt.rcParams.update({"font.size": 14})
    alignment = {"sandwich_first": [], "coffee_first": [], "interleave": []}
    if os.path.isfile("min_distances.json"):
        min_distances = json.load(open("min_distances.json"))
        for key, value in min_distances.items():
            alignment[key.split("||")[-1].split(" ")[-1]].append(value)
    else:
        min_distances = {}
    controller = ai2thor.controller.Controller(
        platform=CloudRendering,
        scene="FloorPlan5",
        width=1440,
        height=810,
        gridSize=0.05,
        snapToGrid=False,
        fieldOfView=60,
    )
    for json_file in glob("results/*.json"):
        action_logs = json.load(open(json_file, "r"))["actions"]
        for key, actions in action_logs.items():
            if (
                key.split(" ")[-1] in alignment.keys()
                and key.startswith("FloorPlan")
                and "{}||{}".format(json_file, key) not in min_distances.keys()
            ):
                try:
                    controller.reset(
                        scene=key.split(" ")[0],
                        width=1440,
                        height=810,
                        gridSize=0.05,
                        snapToGrid=False,
                        fieldOfView=60,
                    )
                    state = controller.step(action="Teleport")
                    checklist = SandwichChecklist()
                    for t, action in tqdm(actions, desc=key):
                        state = controller.step(**action)
                        checklist(state)
                    controller.step(action="Done")
                    mode = key.split(" ")[-1]
                    edit_distance = default_sequences[mode].edit_distance(
                        checklist.checked_sequence
                    )
                    alignment[mode].append(edit_distance)
                    min_distances["{}||{}".format(json_file, key)] = edit_distance
                    json.dump(min_distances, open("min_distances.json", "w"))
                except Exception as e:
                    print("{} {} crashed because {}".format(json_file, key, e))

    matching = json.load(open("matching.json"))
    personalized = []
    for key, dist in min_distances.items():
        json_file = key.split("||")[0]
        matched = key.split(" ")[-1]
        if matching[json_file][1] == matched:
            personalized.append(dist)

    boxplot = plt.boxplot(
        [
            alignment["coffee_first"],
            alignment["sandwich_first"],
            alignment["interleave"],
            personalized,
        ],
        widths=0.8,
        patch_artist=True,
    )
    for patch, color in zip(
        boxplot["boxes"], ["pink", "lightblue", "lightgreen", "orchid"]
    ):
        patch.set_facecolor(color)
    plt.legend(
        boxplot["boxes"],
        ["coffee first", "sandwich first", "interleave", "personalized"],
    )
    plt.xlim(0, 8)
    plt.ylim(-0.5, 25)
    plt.xticks([])
    plt.ylabel("minium editing distance")
    plt.xlabel("different agents")
    for i, name in enumerate(["coffee_first", "sandwich_first", "interleave"]):
        plt.plot(
            [i + 1, i + 1, 4, 4],
            [18.5 + 2 * i, 18.8 + 2 * i, 18.8 + 2 * i, 18.5 + 2 * i],
            color="black",
        )
        plt.text(
            2.25 + i / 2, 19 + 2 * i, annotate(ttest_ind(alignment[name], personalized))
        )
    plt.tight_layout()
    plt.savefig(png_file)


def get_matchings():

    pid2mode = {}
    controller = ai2thor.controller.Controller(
        platform=CloudRendering,
        scene="FloorPlan5",
        width=1440,
        height=810,
        gridSize=0.05,
        snapToGrid=False,
        fieldOfView=60,
    )
    for json_file in glob("results/*.json"):
        action_logs = json.load(open(json_file, "r"))["actions"]
        print(json_file)
        for key, actions in action_logs.items():
            if "train" in key:
                try:
                    controller.reset(
                        scene="FloorPlan5",
                        width=1440,
                        height=810,
                        gridSize=0.05,
                        snapToGrid=False,
                        fieldOfView=60,
                    )
                    state = controller.step(action="Teleport")
                    checklist = SandwichChecklist()
                    for t, action in tqdm(actions, desc=key):
                        state = controller.step(**action)
                        checklist(state)
                    controller.step(action="Done")
                except Exception as e:
                    print("{} {} crashed because {}".format(json_file, key, e))
                else:
                    edit_distance = min(
                        default_sequences.keys(),
                        key=lambda mode: default_sequences[mode].edit_distance(
                            checklist.checked_sequence
                        ),
                    )
                    completed_old, distance_old = pid2mode.get(json_file, (0, 0))
                    completed_new = sum(checklist.tasks.__dict__.values())
                    if completed_new >= completed_old:
                        pid2mode[json_file] = (completed_new, edit_distance)
                    json.dump(pid2mode, open("matching.json", "w"))
    pprint(pid2mode)


def draw_surveys(png_file: str):

    responses = parse_all_surveys()
    plt.rcParams.update({"font.size": 20})
    matching = json.load(open("matching.json"))
    for (q, label), x_pos in zip(
        enumerate(["difficulty", "reasonable", "helpful", "follow"]), range(4, 50, 12)
    ):
        data = [[res[mode][q] + 1 for res in responses] for mode in range(1, 4)]
        data.append(
            [getattr(res, matching[res.json_file][1])[q] + 1 for res in responses]
        )
        boxplot = plt.boxplot(
            data,
            positions=[x_pos + i for i in range(0, 2 * len(data), 2)],
            widths=1.6,
            patch_artist=True,
        )
        for patch, color in zip(
            boxplot["boxes"], ["pink", "lightblue", "lightgreen", "orchid"]
        ):
            patch.set_facecolor(color)

        for i, height in enumerate([7.5, 8.3, 9.1]):
            plt.plot(
                [x_pos + 2 * i, x_pos + 2 * i, x_pos + 6, x_pos + 6],
                [height, height + 0.1, height + 0.1, height],
                color="black",
            )
            plt.text(
                x_pos + 2 + i, height + 0.2, annotate(ttest_ind(data[i], data[-1]))
            )

    plt.legend(
        boxplot["boxes"],
        ["coffee first", "sandwich first", "interleave", "personalized"],
    )
    fig = plt.gcf()
    fig.set_size_inches(16, 5.5)
    plt.xlim(0, 64)
    plt.xticks(range(7, 50, 12), ["difficulty", "reasonable", "helpful", "followed"])
    plt.ylim(0.5, 10)
    plt.yticks([1, 7], ["strongly\ndisagree", "strongly\nagree"])

    plt.tight_layout()
    plt.savefig(png_file)


def test():
    pass


if __name__ == "__main__":
    fire.Fire()
