from __future__ import annotations

from dataclasses import dataclass


STANDARD_DEFAULT = ["GSM8k", "DROP", "MMLU", "ARC", "HellaSwag", "Winogrande", "BoolQ", "MATH"]
STANDARD_HEAVY_FIRST = ["MATH", "GSM8k", "DROP", "MMLU", "HellaSwag", "ARC", "Winogrande", "BoolQ"]

DFM_DEFAULT = [
    "danish_citizen_tests",
    "dala",
    "gec_dala",
    "wmt24pp_en_da",
    "multi_wiki_qa",
    "piqa",
    "generative_talemaader",
    "govreport",
    "nordjyllandnews",
    "humaneval",
]
DFM_HEAVY_FIRST = [
    "govreport",
    "wmt24pp_en_da",
    "generative_talemaader",
    "nordjyllandnews",
    "humaneval",
    "gec_dala",
    "multi_wiki_qa",
    "danish_citizen_tests",
    "dala",
    "piqa",
]

EUROEVAL_GROUPS = [
    "angry-tweets",
    "scala-da",
    "dansk",
    "multi-wiki-qa-da",
    "nordjylland-news",
    "danske-talemaader",
    "danish-citizen-tests",
    "hellaswag-da",
    "ifeval-da",
    "valeu-da",
    "sst5",
    "scala-en",
    "conll-en",
    "squad",
    "cnn-dailymail",
    "life-in-the-uk",
    "hellaswag",
    "ifeval",
    "bfcl-v2",
    "valeu-en",
]


@dataclass(frozen=True)
class BatchDefaults:
    standard: int = 8
    dfm: int = 8
    ifeval: int = 16
    euroeval: int = 4


def standard_shards(task: str) -> int:
    return {
        "ARC": 1,
        "Winogrande": 1,
        "BoolQ": 1,
        "HellaSwag": 2,
        "DROP": 4,
        "MMLU": 4,
        "GSM8k": 8,
        "MATH": 64,
    }.get(task, 1)


def dfm_shards(task: str) -> int:
    return {
        "danish_citizen_tests": 1,
        "dala": 1,
        "piqa": 1,
        "gec_dala": 2,
        "multi_wiki_qa": 2,
        "humaneval": 4,
        "wmt24pp_en_da": 8,
        "generative_talemaader": 8,
        "nordjyllandnews": 8,
        "govreport": 16,
    }.get(task, 1)


def dfm_suite(task: str) -> str:
    suites = {
        "danish_citizen_tests": "hrm_danish_danish_citizen_tests",
        "dala": "hrm_danish_dala",
        "gec_dala": "hrm_danish_gec_dala",
        "wmt24pp_en_da": "hrm_danish_wmt24pp_en_da",
        "multi_wiki_qa": "hrm_danish_multi_wiki_qa",
        "piqa": "hrm_danish_piqa",
        "generative_talemaader": "hrm_danish_generative_talemaader",
        "govreport": "hrm_summarization_govreport",
        "nordjyllandnews": "hrm_summarization_nordjyllandnews",
        "humaneval": "hrm_code_humaneval_local",
    }
    return suites[task]


def ifeval_suite(shard: int, shards: int) -> str:
    if shards == 4:
        return f"hrm_danish_ifeval_da_shard_{shard}_of_4"
    if shards == 8:
        return f"hrm_danish_ifeval_da_shard_{shard}"
    if shards == 16:
        return f"hrm_danish_ifeval_da_shard_{shard}_of_16"
    if shards == 32:
        return f"hrm_danish_ifeval_da_shard_{shard}_of_32"
    raise ValueError(f"Unsupported DFM IFEval shard count: {shards}")
