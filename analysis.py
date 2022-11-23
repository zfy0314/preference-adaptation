import json
import os
from collections import namedtuple
from datetime import datetime, timedelta
from glob import glob
from typing import List, Tuple

import ai2thor.controller
import cv2
import fire
from ai2thor.platform import CloudRendering
from matplotlib import pyplot as plt
from tqdm import tqdm


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
                if not key.startswith("<class_tutorial"):
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
                    except:  # noqa
                        print("crashed!")


PostTestSurvey = namedtuple(
    "PostTestSurvey", ["easy", "attention", "follow", "helpful", "reasonable"]
)
Participant = namedtuple(
    "Participant", ["simulator", "coffee_first", "sandwich_first", "interleave"]
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
    )


def parse_all_surveys() -> List[Participant]:
    return [parse_survey(json_file) for json_file in glob("results/*.json")]


def draw_surveys(question: int, ylabel: str, png_file: str):

    responses = parse_all_surveys()
    data = [[res[mode][question] + 1 for res in responses] for mode in range(1, 4)]
    plt.xlim(0, 5)
    boxplot = plt.boxplot(
        data,
        patch_artist=True,
    )
    for patch, color in zip(boxplot["boxes"], ["pink", "lightblue", "lightgreen"]):
        patch.set_facecolor(color)
    plt.xticks(
        range(1, 5),
        [
            "coffee first",
            "sandwich first",
            "interleave",
            "personalized\n [to be filled]",
        ],
    )
    fig = plt.gcf()
    fig.set_size_inches(6, 6)
    plt.ylim(0, 8)
    plt.ylabel(ylabel)
    plt.savefig(png_file)


def test():
    pass


if __name__ == "__main__":
    fire.Fire()
