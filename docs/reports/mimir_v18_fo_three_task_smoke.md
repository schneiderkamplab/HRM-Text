# Mimir v1.8 (DFM-Mimir-v1.8): Faroese three-task smoke

**Checkpoint:** `dfm15/XL-from-dfm14-epoch1`, `step_3800000`, EMA
(HF export: `/work/dfm/euroeval-runs/mimir-v1.8-3800000-validation/model`, published as
`danish-foundation-models/DFM-Mimir-v1.8`).
**Backend:** Transformers `HrmTextForCausalLM` on CPU (BF16/SDPA, 64 threads), training
Gemma chat template, thinking disabled, no system prompt.
**Decoding:** greedy, batch one; 768 new tokens for the story, 384 for correction/summary;
no repetition penalty. Prompts, budgets and template match
`xl_2990k_multilingual_smoke_review.md` for direct comparability.
**Review:** assistant qualitative read; not a native-speaker certification.

## Prompts and responses

## grammatical_error_correction

**Prompt**

Rætta mállærufeilin í hesum setningi. Svara bara við rættaða setninginum: Tey trý børnini spæla í urtagarðinum, meðan mamma teirra lesur ein bók.

**Response (verbatim)**

```text
Tey trý børnini spæla í urtagarðinum, meðan mamma teirra lesur eina bók.
```

**Generation:** 29 tokens; finish=stop.

## creative_writing

**Prompt**

Skriva eina stutta søgu á føroyskum um eina ont, sum verður rúmdarfari. Á fyrstu rúmdarferðini varnast ontin, at ein týðandi knøttur bara kann trýstast inn við einum nevi. Søgan skal hava eina samrøðu, eina óvæntaða forðing og ein góðan enda.

**Response (verbatim)**

```text
Tað var ein gongd ein ont, sum var sera spennandi á rúmdarferð. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarfari. Hon var so spennandi, at hon vildi vera rúmdarf
```

**Generation:** 768 tokens; finish=length.

## summarization

**Prompt**

Tak saman um hendan tekstin á føroyskum í júst tveimum setningum. Tak bæði broytingina og týdningarmesta úrslitið við, og legg ikki nýggjar upplýsingar afturat.

Í apríl fór bókasavnið í býnum at hava opið tvey kvøld um vikuna. Royndin skuldi gera tað lættari hjá fólki við longum arbeiðsdøgum at læna bøkur. Eftir tríggjar mánaðir var talið á vitjandi um kvøldið vaksið støðugt, meðan talið fyrrapart næstan var óbroytt. Fleiri lesibólkar í býnum vóru eisini farnir at hittast á bókasavninum. Býráðið gjørdi tí av at halda fram við skipanini restina av árinum.

**Response (verbatim)**

```text
Bókasavnið í býnum fór at hava opið tvey kvøld um vikuna fyri at gera tað lættari hjá fólki við longum arbeiðsdøgum at læna bøkur. Eftir tríggjar mánaðir var talið á vitjandi um kvøldið vaksið støðugt, og býráðið gjørdi av at halda fram við skipanini restina av árinum.
```

**Generation:** 104 tokens; finish=stop.

## Assessment

- **grammatical_error_correction** — Correct repair (`ein bók` → `eina bók`), 29 tokens,
  clean stop. Equivalent to the XL 2990K result (task/language/fluency 3/3/3).
- **creative_writing** — Severe repetition loop (`Hon var so spennandi, at hon vildi vera
  rúmdarfari.` repeated to the 768-token cap). No conversation, obstacle or ending.
  Same failure mode as XL 2990K (score 0 there).
- **summarization** — Two sentences, faithful: evening openings to help long-workday
  borrowers, growth in evening visitors, council decision to continue. No invented
  details. Comparable to XL 2990K (score 2 there).

Conclusion: Mimir v1.8 reproduces the 2990K Faroese profile — strong short-form
correction, serviceable summary, unreliable open-ended story generation.
