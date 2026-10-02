"""Build v1.5 release documentation from verified epoch-10 artifacts; no upload."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from backfill_external_eval_to_wandb import collect_standard, collect_dfm, collect_euroeval

V1 = 'danish-foundation-models/DFM-Mimir'
V1_REV = '2fbf6ea5ce8794ee1f2684939a579d4741b4ca7a'
OUT = ROOT / 'logs/releases/DFM-Mimir-v1.5'
EXPORT = ROOT / 'exports/dfm11_XL_epoch10_epoch_10_ema_hf'
GROUPS = {
    'English': [
        ('BoolQ accuracy (standard)', 'eval/BoolQ/acc', 100),
        ('Winogrande accuracy (standard)', 'eval/Winogrande/acc', 100),
        ('HellaSwag accuracy (standard)', 'eval/HellaSwag/acc', 100),
        ('MMLU accuracy (standard)', 'eval/MMLU/acc', 100),
        ('ARC accuracy (standard)', 'eval/ARC/acc', 100),
        ('DROP F1 (standard)', 'eval/DROP/f1', 100),
        ('GovReport ROUGE-1 (DFM)', 'dfm_eval/govreport/rouge1/mean', 100),
    ],
    'Math & Code': [
        ('GSM8K accuracy (standard)', 'eval/GSM8k/acc', 100),
        ('MATH accuracy (standard)', 'eval/MATH/acc', 100),
        ('HumanEval sanitized accuracy (DFM)', 'dfm_eval/humaneval/verify_sanitized/accuracy', 100),
    ],
    'Danish': [
        ('AngryTweets macro F1 (EuroEval)', 'euroeval/da/sentiment-classification/angry-tweets/macro_f1', 1),
        ('DaLA macro F1 (DFM)', 'dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1', 100),
        ('GEC-DaLA exact match (DFM)', 'dfm_eval/gec_dala/exact_match/mean', 100),
        ('PIQA-DA accuracy (DFM)', 'dfm_eval/piqa/piqa_scorer/accuracy', 100),
        ('Daisy / generative idioms judge accuracy (DFM)', 'dfm_eval/generative-talemaader/model_graded_fact/accuracy', 100),
        ('MultiWikiQA exact match (DFM)', 'dfm_eval/multi_wiki_qa/exact_match/mean', 100),
        ('WMT24++ en-da chrF3++ (DFM)', 'dfm_eval/wmt24pp-en-da/chrf3pp/mean', 100),
        ('NordjyllandNews chrF3++ (DFM)', 'dfm_eval/nordjyllandnews/chrf3pp/mean', 1),
        ('IFEval-DA prompt strict accuracy (DFM)', 'dfm_eval/ifeval-da/instruction_following/prompt_strict_acc', 100),
        ('HellaSwag-DA accuracy (EuroEval)', 'euroeval/da/common-sense-reasoning/hellaswag-da/accuracy', 1),
    ],
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('LICENSE', 'DFM-logo.png'):
        shutil.copy2(hf_hub_download(V1, name, revision=V1_REV), OUT / name)
    roots = [ROOT / f'logs/{suite}/dfm11_XL_epoch10/epoch_10'
             for suite in ('eval', 'dfm_evals', 'euroeval')]
    metrics = {**collect_standard(roots[0]), **collect_dfm(roots[1]), **collect_euroeval(roots[2])}
    sections, averages, selected = [], {}, {}
    for section, entries in GROUPS.items():
        lines = [f'### {section}', '', '| Benchmark / metric | Score (0-100) |', '|---|---:|']
        scores = []
        for label, key, scale in entries:
            score = metrics[key] * scale
            assert 0 <= score <= 100, (key, score)
            lines.append(f'| {label} | {score:.2f} |')
            scores.append(score)
            selected[key] = {'raw_value': metrics[key], 'display_scale': scale, 'score': score}
        averages[section] = sum(scores) / len(scores)
        lines.append(f'| **Unweighted mean of rows above** | **{averages[section]:.2f}** |')
        sections.append('\n'.join(lines))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(list(averages), list(averages.values()), color=['#25838b', '#b95463', '#5b8e45'])
    ax.bar_label(bars, fmt='%.2f', padding=4)
    ax.set_ylim(0, 100)
    ax.set_ylabel('Mean of the model-card metrics (0-100)')
    ax.set_title('DFM Mimir v1.5 - epoch 10 EMA')
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    (OUT / 'plots').mkdir(exist_ok=True)
    fig.savefig(OUT / 'plots/subject_avg_scores.png', dpi=180)
    plt.close(fig)
    card = '''---
library_name: transformers
license: apache-2.0
license_name: apache-2.0
license_link: LICENSE
language:
  - da
  - en
pipeline_tag: text-generation
tags:
  - danish
  - english
  - hrm-text
  - instruction-tuned
  - prefix-lm
---

<div align="center">
  <img src="DFM-logo.png" alt="Danish Foundation Models" width="400"/>
</div>

# DFM Mimir v1.5

DFM Mimir v1.5 is the final epoch-10 **EMA** checkpoint of the XL HRM-Text
training lineage, at **2,877,261 optimizer steps**. It continues the Danish and
English Mimir model family on subsequent dataset mixtures, ending with DFM11.
It is a continuation checkpoint, not a new model trained from scratch for ten
identical epochs. It is not an XXL model.

The architecture has approximately **0.981B non-embedding/head parameters**,
or **1.787B total parameters** including its separate 262,144-token input
embedding and output head. The family is historically described as a 1B model.
This repository contains BF16 inference weights, not optimizer state or a
resumable FSDP training checkpoint.

## Model details

| Property | Value |
|---|---|
| Architecture | HRM-Text XL, PrefixLM |
| Total parameters | 1,786,775,040 |
| Parameters excluding input embedding and output head | 981,468,672 |
| Hidden dimension | 1,536 |
| Stored transformer layers | 16, reused across recurrent cycles |
| Attention heads | 12 |
| H / L cycles | 2 / 3; six L and two H executions per complete reasoning pass |
| Vocabulary | 262,144 |
| Context length | 4,096 |
| Weight dtype | BF16 |
| Exported weights | EMA, epoch 10, step 2,877,261 |
| Final epoch dataset | DFM11, 103,214,604,702 sampled tokens |
| Final base learning rate | 1e-5, with automatic H/L module scaling |
| License | Apache 2.0 |

The final-epoch token count is not a claim about every preceding epoch or the
total training-token budget. Earlier epochs used different mixtures.

## Evaluation

The following scores come from the completed production evaluation of this
exact epoch-10 EMA export. Each row names its suite and metric; accuracy/F1/
ROUGE/normalized chrF values are expressed on a 0-100 scale. The plot averages
the individual rows in each section, not suite averages or W&B headline averages.

![Mean scores by subject area](plots/subject_avg_scores.png)

{tables}

### Evaluation caveats

- These tables use the current production evaluation protocols. They are not
  a controlled re-evaluation of the comparison models in the v1 card. Do not
  compare similarly named tasks across suites as if prompts and scorers match.
- In particular AngryTweets is macro F1 here, and HellaSwag-DA is EuroEval;
  the original v1 card used different reported metrics/protocols for some rows.
- The very low generative-idiom/Daisy score is retained as measured, not omitted
  from the mean. It is a judge-based task and is not the EuroEval multiple-choice
  Danish idioms benchmark.
- Standard Winogrande here is distinct from DFM's zero-shot Winogrande. The
  latter has known formatting/truncation and duplicate-shard issues in this
  evaluation pipeline and is not used in this table.
- `evaluation_results.json` records the raw merged metric keys and values,
  table scaling, and source-artifact checksums for this release.

## Usage instructions

Use a Transformers/vLLM build with native `hrm_text` / `HrmTextForCausalLM`
support and the HRM **PrefixLM attention** implementation. A generic causal-only
decoder or a build without this architecture is not an equivalent runtime.
See the [training and evaluation repository](https://github.com/schneiderkamplab/HRM-Text)
for the compatible export and serving path. No standalone remote model code is
bundled here, matching the v1 package.

- Use the supplied Gemma 4 tokenizer and `chat_template.jinja`; do not substitute
  a generic chat template. Keep `enable_thinking=False` when reproducing the
  non-thinking evaluation prompts.
- Respect the 4,096-token context limit and PrefixLM prompt masking.
- The uploaded files preserve the production export exactly, including
  **`fix_mistral_regex=true`**. Training tokenization used the unpatched tokenizer
  graph; a separate 2750K comparison established that changing this flag can
  change token IDs and scores. These epoch-10 scores are for the uploaded
  fix-enabled export, not a training-tokenizer/no-fix re-evaluation. Do not
  silently change the flag when comparing these published results.
- Generated code is untrusted and should be executed only in a sandbox.

## Technical report

The original model-family report is
[DFM Mimir v1](https://arxiv.org/abs/2608.13517). It describes the earlier
release, not all additional data, training steps or results of v1.5. Training
uses the [HRM-Text fork](https://github.com/schneiderkamplab/HRM-Text).

## Memorisation audit

The v1 report and [v1 model card](https://huggingface.co/danish-foundation-models/DFM-Mimir)
describe two memorisation audits of that release. Those numerical findings
must not be treated as measurements of this later checkpoint. No new
checkpoint-specific memorisation audit is supplied with v1.5.

## Limitations

The model is primarily intended for Danish and English. It may hallucinate,
produce incorrect code or reasoning, fail format constraints, and reproduce
social biases. It is not guaranteed safe or reliable for high-stakes uses.
The v1 safety and memorisation findings do not certify the v1.5 weights.
Benchmark results depend on the tokenizer, template, generation limits,
answer extraction and judge implementation.

## License

This model is released under the **Apache License 2.0**. See [LICENSE](LICENSE).
The license and DFM logo are carried over from the original DFM-Mimir package.

## Project partners & funding

The Mimir project was developed in collaboration between
[University of Southern Denmark](https://www.sdu.dk/en/forskning/machine-learning),
[Aarhus University](https://chc.au.dk/), [University of Copenhagen](https://www.ku.dk/en)
and the [Alexandra Institute](https://alexandra.dk/), as part of
[Danish Foundation Models](https://foundationmodels.dk/).
The original project acknowledges funding from the
[Ministry of Science, Higher Education and Digital Affairs](https://ufm.dk/en).

## How to cite

For the model family, cite the v1 report and additionally identify this
repository and its pinned revision when reporting v1.5 results:

```bibtex
@misc{schneiderkamp2026dfmmimirv1open,
  title={DFM Mimir v1: An Open HRM Delivering Frontier Performance at 1B Parameters Using Only Permissible Post-Training Data},
  author={Peter Schneider-Kamp and Jacob Nielsen and Gianluca Barmina and Kenneth Enevoldsen and Lukas Galke Poech},
  year={2026},
  eprint={2608.13517},
  archivePrefix={arXiv},
  primaryClass={cs.CL},
  url={https://arxiv.org/abs/2608.13517}
}
```
'''
    (OUT / 'README.md').write_text(card.replace('{tables}', '\n\n'.join(sections)))
    sources = {}
    for root in roots:
        for path in sorted(root.rglob('*metrics.json')):
            if path.name not in ('merged_metrics.json', 'merged_ifeval_da_metrics.json'):
                continue
            sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = dict(checkpoint='epoch_10', step=2877261, weights='ema', fix_mistral_regex=True,
                  selected_metrics=selected, section_means=averages, metrics=metrics,
                  source_sha256=sources, inherited_assets_revision=V1_REV)
    (OUT / 'evaluation_results.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(averages, indent=2))
    print(OUT)


if __name__ == '__main__':
    main()
