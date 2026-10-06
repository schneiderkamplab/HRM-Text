from __future__ import annotations

from dataclasses import dataclass


STANDARD_DEFAULT = ["GSM8k", "DROP", "MMLU", "ARC", "HellaSwag", "Winogrande", "BoolQ", "MATH"]
STANDARD_HEAVY_FIRST = ["MATH", "GSM8k", "DROP", "MMLU", "HellaSwag", "ARC", "Winogrande", "BoolQ"]

DFM_DEFAULT = [
    "andersen_modernization",
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
    "arc_easy",
    "arc_challenge",
    "boolq",
    "commonsense_qa",
    "hellaswag",
    "piqa_en",
    "winogrande",
    "openbookqa",
    "socialiqa",
    "squad",
    "drop",
    "coqa",
    "nq_open",
    "triviaqa",
    "humaneval_plus",
    "mbpp",
    "mbpp_plus",
    "mmlu_pro",
    "agieval",
    "bbh",
]
DFM_HEAVY_FIRST = [
    "mbpp",
    "mbpp_plus",
    "humaneval_plus",
    "triviaqa",
    "mmlu_pro",
    "bbh",
    "coqa",
    "drop",
    "squad",
    "nq_open",
    "agieval",
    "hellaswag",
    "boolq",
    "arc_easy",
    "socialiqa",
    "arc_challenge",
    "commonsense_qa",
    "piqa_en",
    "winogrande",
    "openbookqa",
    "govreport",
    "wmt24pp_en_da",
    "generative_talemaader",
    "nordjyllandnews",
    "humaneval",
    "gec_dala",
    "multi_wiki_qa",
    "danish_citizen_tests",
    "dala",
    "andersen_modernization",
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
    "sst5",
    "scala-en",
    "conll-en",
    "squad",
    "cnn-dailymail",
    "life-in-the-uk",
    "hellaswag",
    "ifeval",
    "bfcl-v2",
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
        "andersen_modernization": 1,
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
        "arc_easy": 2,
        "arc_challenge": 1,
        "boolq": 2,
        "commonsense_qa": 1,
        "hellaswag": 2,
        "piqa_en": 1,
        "winogrande": 2,
        "openbookqa": 1,
        "socialiqa": 2,
        "squad": 4,
        "drop": 2,
        "coqa": 1,
        "nq_open": 4,
        "triviaqa": 8,
        "humaneval_plus": 4,
        "mbpp": 4,
        "mbpp_plus": 4,
        "mmlu_pro": 4,
        "agieval": 2,
        "bbh": 4,
    }.get(task, 1)


def dfm_suite(task: str) -> str:
    suites = {
        "andersen_modernization": "hrm_danish_andersen_modernization",
        "danish_citizen_tests": "hrm_danish_danish_citizen_tests",
        "dala": "hrm_danish_dala",
        "gec_dala": "hrm_danish_gec_dala",
        "wmt24pp_en_da": "hrm_danish_wmt24pp_en_da",
        "multi_wiki_qa": "hrm_danish_multi_wiki_qa",
        "piqa": "hrm_danish_piqa",
        "generative_talemaader": "hrm_danish_generative_talemaader",
        "govreport": "hrm_summarization_govreport",
        "govreport_long": "hrm_long_context_govreport",
        "nordjyllandnews": "hrm_summarization_nordjyllandnews",
        "humaneval": "hrm_code_humaneval_local",
        "arc_easy": "hrm_mc9_arc_easy",
        "arc_challenge": "hrm_mc9_arc_challenge",
        "boolq": "hrm_mc9_boolq",
        "commonsense_qa": "hrm_mc9_commonsense_qa",
        "hellaswag": "hrm_mc9_hellaswag",
        "piqa_en": "hrm_mc9_piqa_en",
        "winogrande": "hrm_mc9_winogrande",
        "openbookqa": "hrm_mc9_openbookqa",
        "socialiqa": "hrm_mc9_socialiqa",
        "squad": "hrm_gen5_squad",
        "drop": "hrm_gen5_drop",
        "coqa": "hrm_gen5_coqa",
        "nq_open": "hrm_gen5_nq_open",
        "triviaqa": "hrm_gen5_triviaqa",
        "humaneval_plus": "hrm_code4_humaneval_plus",
        "mbpp": "hrm_code4_mbpp",
        "mbpp_plus": "hrm_code4_mbpp_plus",
        "mmlu_pro": "hrm_flex_mmlu_pro",
        "agieval": "hrm_flex_agieval",
        "bbh": "hrm_flex_bbh",
        "ruler_smoke": "hrm_long_context_ruler_smoke",
        "ruler_8k": "hrm_long_context_ruler_8k",
        "longbench_en": "hrm_long_context_longbench_en",
        "longalign_en": "hrm_long_context_longalign_en",
        "longalign_da": "hrm_long_context_longalign_da",
        "marathon": "hrm_long_context_marathon",
        "qmsum_cleaned": "hrm_long_context_qmsum",
        "danish_summarization_eur_lex": "hrm_long_context_danish_summarization_eur_lex",
        "danish_summarization": "hrm_long_context_danish_summarization",
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
LONG_CONTEXT_EXTRA_TASKS = (
    "longbench_en",
    "longalign_en",
    "longalign_da",
    "marathon",
    "qmsum_cleaned",
    "danish_summarization_eur_lex",
    "danish_summarization",
)
