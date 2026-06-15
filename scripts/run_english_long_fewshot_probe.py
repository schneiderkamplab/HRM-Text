#!/usr/bin/env python
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.engines import SimpleEngine


def build_fewshot_prompts(target_prompts: list[str]) -> list[str]:
    examples = [
        [
            (
                "Continue the following educational text with one additional coherent paragraph that explains what happens when metal is left in the rain.\n\n"
                "Iron is a strong metal used in tools, bridges, and machines. When iron is exposed to air and water for a long time, it can react with oxygen. This reaction forms rust, a reddish-brown material that is weaker than the original metal.",
                "When metal is left in the rain, water and oxygen can keep reacting with its surface. Over time, more rust forms, the metal becomes weaker, and objects made from it may bend, crack, or stop working properly.",
            ),
            (
                "Continue the following educational text with one additional coherent paragraph that explains what happens when bread dough is heated in an oven.\n\n"
                "Bread dough contains flour, water, yeast, and sometimes salt or sugar. Yeast produces gas bubbles while the dough rises. The stretchy gluten network helps trap those bubbles before baking.",
                "When bread dough is heated in an oven, the trapped gas expands and the dough rises further. The heat also firms the gluten and starches, creating a soft interior and a browned crust.",
            ),
            (
                "Continue the following educational text with one additional coherent paragraph that explains what happens when a pond freezes in winter.\n\n"
                "A pond is a small body of water that can support plants, insects, fish, and other animals. During cold weather, the water at the surface loses heat to the air. Ice may begin forming when the surface reaches the freezing point.",
                "When a pond freezes in winter, ice usually forms first on the surface. This layer slows further heat loss, so liquid water can remain underneath and many aquatic organisms can survive until warmer weather returns.",
            ),
        ],
        [
            (
                "Summarize the following text in exactly two sentences.\n\n"
                "Honeybees live together in colonies with a queen, workers, and drones. Worker bees collect nectar and pollen from flowers. They also help care for young bees and protect the hive. Pollination happens when pollen is moved between flowers, allowing many plants to make seeds and fruit.",
                "Honeybees live in organized colonies where worker bees gather food, protect the hive, and care for young bees. As they visit flowers, they move pollen between plants and help many plants produce seeds and fruit.",
            ),
            (
                "Summarize the following text in exactly two sentences.\n\n"
                "Volcanoes form where molten rock reaches Earth's surface. Some eruptions release slow-moving lava, while others send ash and gas high into the air. Over time, repeated eruptions can build mountains and create new land.",
                "Volcanoes form when molten rock reaches Earth's surface and erupts as lava, ash, or gas. Repeated eruptions can build mountains and create new land over time.",
            ),
            (
                "Summarize the following text in exactly two sentences.\n\n"
                "Public libraries give people access to books, computers, quiet study spaces, and community programs. Many libraries also help visitors find reliable information. These services can support learning for children, students, and adults.",
                "Public libraries provide books, technology, study spaces, programs, and help finding reliable information. These services support learning for people of many ages.",
            ),
        ],
        [
            (
                "Rewrite the following text in the past tense while preserving the meaning.\n\n"
                "The river carries water from the mountains to the valley. It flows past farms and towns. People use the water for drinking, irrigation, and small boats.",
                "The river carried water from the mountains to the valley. It flowed past farms and towns. People used the water for drinking, irrigation, and small boats.",
            ),
            (
                "Rewrite the following text in the past tense while preserving the meaning.\n\n"
                "The telescope helps astronomers observe distant planets. It collects light through a large mirror. Computers turn the measurements into images.",
                "The telescope helped astronomers observe distant planets. It collected light through a large mirror. Computers turned the measurements into images.",
            ),
            (
                "Rewrite the following text in the past tense while preserving the meaning.\n\n"
                "The team tests the bridge before opening it. Engineers measure how the structure responds to weight and wind. They record the results carefully.",
                "The team tested the bridge before opening it. Engineers measured how the structure responded to weight and wind. They recorded the results carefully.",
            ),
        ],
        [
            (
                "Rewrite the following text for a 10-year-old. Keep it clear and friendly, and do not add facts that are not in the text.\n\n"
                "Evaporation occurs when liquid water gains enough energy for some molecules to leave the surface and become water vapor.",
                "Evaporation happens when water gets enough energy to turn from a liquid into a gas called water vapor.",
            ),
            (
                "Rewrite the following text for a 10-year-old. Keep it clear and friendly, and do not add facts that are not in the text.\n\n"
                "A microscope magnifies tiny objects so people can see details that are too small for the unaided eye.",
                "A microscope makes tiny things look bigger, so people can see details that are too small to see with just their eyes.",
            ),
            (
                "Rewrite the following text for a 10-year-old. Keep it clear and friendly, and do not add facts that are not in the text.\n\n"
                "A compass contains a magnetized needle that points toward Earth's magnetic north.",
                "A compass has a special magnetic needle that points toward Earth's magnetic north.",
            ),
        ],
        [
            (
                "Extract five key facts from the following text as a numbered list. Each fact should be one sentence.\n\n"
                "Bats are mammals that can fly. Many bats hunt insects at night. Some bats use echoes to find food in the dark. Bats often rest in caves, trees, or buildings during the day. They can help ecosystems by eating insects or spreading seeds.",
                "1. Bats are mammals that can fly.\n2. Many bats hunt insects at night.\n3. Some bats use echoes to find food in the dark.\n4. Bats often rest in caves, trees, or buildings during the day.\n5. Bats can help ecosystems by eating insects or spreading seeds.",
            ),
            (
                "Extract five key facts from the following text as a numbered list. Each fact should be one sentence.\n\n"
                "The Moon orbits Earth. Its gravity helps create ocean tides. The Moon reflects sunlight, which makes it visible at night. Its surface has craters made by impacts. Astronauts first walked on the Moon in 1969.",
                "1. The Moon orbits Earth.\n2. The Moon's gravity helps create ocean tides.\n3. The Moon reflects sunlight, which makes it visible at night.\n4. The Moon's surface has craters made by impacts.\n5. Astronauts first walked on the Moon in 1969.",
            ),
            (
                "Extract five key facts from the following text as a numbered list. Each fact should be one sentence.\n\n"
                "Coral reefs are built by tiny animals called coral polyps. Reefs provide shelter for many ocean species. They grow best in warm, shallow, clear water. Pollution and warming seas can damage reefs. Healthy reefs can also help protect coastlines from waves.",
                "1. Coral reefs are built by tiny animals called coral polyps.\n2. Reefs provide shelter for many ocean species.\n3. Reefs grow best in warm, shallow, clear water.\n4. Pollution and warming seas can damage reefs.\n5. Healthy reefs can help protect coastlines from waves.",
            ),
        ],
    ]
    if len(target_prompts) != len(examples):
        raise ValueError(f"Expected {len(examples)} prompts, got {len(target_prompts)}")

    fewshot_prompts = []
    for prompt, task_examples in zip(target_prompts, examples):
        parts = [
            "Follow the pattern shown in the examples. For the final item, provide only the response.",
            "",
        ]
        for index, (example_prompt, example_response) in enumerate(task_examples, start=1):
            parts.extend(
                [
                    f"Example {index} prompt:",
                    example_prompt,
                    "",
                    f"Example {index} response:",
                    example_response,
                    "",
                ]
            )
        parts.extend(["Final prompt:", prompt, "", "Final response:"])
        fewshot_prompts.append("\n".join(parts))
    return fewshot_prompts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt-path", required=True)
    parser.add_argument("--ckpt-tag", required=True)
    parser.add_argument("--use-ema", action="store_true")
    parser.add_argument("--input", type=Path, default=Path("logs/eval/original_sapient_L_epoch4_english_long_smoke_generations.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-context", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=360)
    args = parser.parse_args()

    source_rows = json.loads(args.input.read_text())
    target_prompts = [row["prompt"] for row in source_rows]
    prompts = build_fewshot_prompts(target_prompts)

    engine = SimpleEngine(
        ckpt_path=args.ckpt_path,
        ckpt_tag=args.ckpt_tag,
        ckpt_use_ema=args.use_ema,
    )
    completions = engine.generate(
        prompts,
        batch_size=args.batch_size,
        max_context=args.max_context,
        max_tokens=args.max_tokens,
        temperature=0.0,
        condition="direct",
    )
    rows = []
    for source, fewshot_prompt, completion in zip(source_rows, prompts, completions):
        rows.append(
            {
                "target_prompt": source["prompt"],
                "fewshot_prompt": fewshot_prompt,
                "completion": completion,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
