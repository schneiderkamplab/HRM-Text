"""Small paired tokenizer replay against existing vLLM weights; never syncs W&B."""
import collections
import json
from pathlib import Path
import random
import re
import urllib.request
import sys

import pyarrow as pa
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs/eval/xl_2750k_tokenizer_replay"
BASE = "http://127.0.0.1:20272"


def request(endpoint, payload=None):
    req = urllib.request.Request(BASE + endpoint, data=None if payload is None else
        json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.load(response)


def normalized(text):
    return " ".join(text.split())


def main():
    OUT.mkdir(exist_ok=True)
    output = OUT / "generations.jsonl"
    assert not output.exists(), "Do not overwrite a previous replay"
    model = request("/v1/models")["data"][0]["id"]
    source = ROOT / "exports/dfm11_XL_epoch10_step_2750000_ema_hf"
    tokenizers = {"fix_on": AutoTokenizer.from_pretrained(source, local_files_only=True),
                  "fix_off": AutoTokenizer.from_pretrained(str(source) + "_training_tokenizer", local_files_only=True)}
    template = (ROOT / "evaluation/chat_templates/gemma4_native_chat.jinja").read_text()
    logroot = ROOT / "logs/euroeval/dfm11_XL_2750k_training_tokenizer/step_2750000/epoch_2"
    rng = random.Random(2750000)
    with output.open("x") as stream:
        for task in ("angry-tweets", "life-in-the-uk", "hellaswag"):
            directory = logroot / task
            gold = {}
            for path in (directory / "cache").rglob("*-val.arrow"):
                for row in pa.ipc.open_stream(path).read_all().to_pylist():
                    gold[normalized(row["text"])] = row["label"]
            candidates = {}
            for line in (directory / "proxy_payloads.jsonl").open():
                payload = json.loads(line).get("outgoing", {})
                messages = payload.get("messages", [])
                if not messages:
                    continue
                prompt = messages[-1]["content"]
                marker = "Dokument: " if task == "angry-tweets" else "Question: "
                tail = normalized(prompt.rsplit(marker, 1)[-1])
                matches = [(text, label) for text, label in gold.items() if tail.startswith(text)]
                if len(matches) == 1:
                    text, label = matches[0]
                    candidates.setdefault(text, dict(messages=messages, gold=label, task=task))
            assert len(candidates) >= 30, (task, len(candidates))
            samples = rng.sample(list(candidates.values()), 30)
            for index, sample in enumerate(samples):
                rendered = tokenizers["fix_off"].apply_chat_template(sample["messages"],
                    chat_template=template, tokenize=False, add_generation_prompt=True)
                ids = {name: tokenizer.encode(rendered, add_special_tokens=False)
                       for name, tokenizer in tokenizers.items()}
                live = request("/tokenize", dict(model=model, messages=sample["messages"], add_generation_prompt=True))
                assert live["tokens"] == ids["fix_off"], "Chat/completion prompt mismatch"
                responses = {}
                for name in ("fix_on", "fix_off"):
                    responses[name] = request("/v1/completions", dict(model=model,
                        prompt=ids[name], max_tokens=10, temperature=0.0))
                row = dict(**sample, index=index, token_lengths={k:len(v) for k,v in ids.items()},
                           responses=responses, longer={})
                labels = ["positiv", "neutral", "negativ"] if task == "angry-tweets" else list("abcd")
                for name, response in responses.items():
                    choice = response["choices"][0]
                    text = choice["text"].strip().lower()
                    if choice["finish_reason"] == "length" or text not in labels:
                        row["longer"][name] = request("/v1/completions", dict(model=model,
                            prompt=ids[name], max_tokens=64, temperature=0.0))
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                print(task, index + 1, sample["gold"],
                      {k:v["choices"][0]["text"] for k,v in responses.items()}, flush=True)


def summarize():
    from Levenshtein import distance
    from sklearn.metrics import f1_score

    rows = [json.loads(line) for line in (OUT / "generations.jsonl").open()]
    report = ["# XL 2750K Paired Tokenizer Replay", "",
        "30 distinct validation examples per task, deterministic seed 2750000; first saved prompt per example.",
        "Same live EMA weights; rendered chat token IDs checked against the server for every prompt.",
        "10-token greedy completions; non-bare labels/length finishes replayed with 64 tokens.",
        "No W&B logging or production changes. Small diagnostic sample, not a replacement benchmark.", ""]
    summary = {}
    for task in ("angry-tweets", "life-in-the-uk", "hellaswag"):
        subset = [r for r in rows if r["task"] == task]
        labels = ["positiv", "neutral", "negativ"] if task == "angry-tweets" else list("abcd")
        gold = [{"positive":"positiv", "negative":"negativ"}.get(r["gold"],r["gold"]) for r in subset]
        summary[task] = {}
        for variant in ("fix_on", "fix_off"):
            texts = [r["responses"][variant]["choices"][0]["text"] for r in subset]
            predicted = []
            for text in texts:
                match = re.search(r"boxed\{(.*?)\}", text)
                text = (match.group(1) if match else text).lower()
                prefix = [label for label in labels if text.startswith(label)]
                predicted.append(prefix[0] if prefix else min(labels,
                    key=lambda label: distance(text,label,weights=(1000,1,1000))))
            stats = dict(correct=sum(a==b for a,b in zip(gold,predicted)), total=len(subset),
                macro_f1=f1_score(gold,predicted,labels=labels,average="macro"),
                bare_labels=sum(t.strip().lower() in labels for t in texts),
                thinking=sum("<think>" in t for t in texts),
                assistant_prefix=sum(t.startswith("assistant:") for t in texts),
                length_finishes=sum(r["responses"][variant]["choices"][0]["finish_reason"]=="length" for r in subset),
                label_counts=dict(collections.Counter(predicted)),
                longer_replays=sum(variant in r["longer"] for r in subset))
            summary[task][variant] = stats
        report += [f"## {task}", "", "```json", json.dumps(summary[task],indent=2), "```", "",
                   "| Sample | Gold | Fix on | Fix off |", "|---|---|---|---|"]
        for index,r in enumerate(subset):
            texts=[r["responses"][v]["choices"][0]["text"].replace("\n"," ").replace("|","\\|") for v in ("fix_on","fix_off")]
            report.append(f"| {index+1} | {gold[index]} | {texts[0]} | {texts[1]} |")
        report += [""]
    (OUT / "summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    (OUT / "report.md").write_text("\n".join(report)+"\n")
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    if "--summarize" in sys.argv:
        summarize()
    else:
        main()
