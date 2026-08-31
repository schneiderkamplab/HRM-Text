# DFM10 Audited Filter-Source Reconciliation

Weights reflect the active prefix policy and 4,097-token sampler contract. Token totals are mean-length estimates; final sampler analytics are authoritative.

| Source | Usable | Tasks | Sampled rows/epoch | Est. tokens/epoch | Decision | Findings |
|---|---:|---:|---:|---:|---|---|
| `GEM/wiki_cat_sum` | 57% | 3 | 0 | 0 | repaired replacement | ungrounded or hallucinated content (64%); scraping, OCR, or encoding noise (28%) |
| `oliverkinch/danmarks-statistik-bt` | 61% | 1 | 0 | 0 | repaired replacement | instruction or output-format mismatch (47%); ungrounded or hallucinated content (17%) |
| `schneiderkamplab/sapient-synth-flan-dialog-fsopt-data-qrecc-ii` | 62% | 1 | 0 | 0 | repaired replacement | truncated or incomplete target (61%); instruction or output-format mismatch (48%) |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task871-msmarco-question-generation` | 63% | 1 | 0 | 0 | exclude negligible low-quality source | instruction or output-format mismatch (52%); truncated or incomplete target (17%) |
| `allenai/code_meta_reasoning` | 60% | 10 | 0 | 0 | repaired replacement | instruction or output-format mismatch (42%); ungrounded or hallucinated content (30%) |
| `oliverkinch/da-instruct-dynaword` | 62% | 1 | 0 | 0 | repaired replacement | truncated or incomplete target (47%); instruction or output-format mismatch (38%) |
| `alexandrainst/dacoref` | 65% | 1 | 0 | 0 | exclude incorrect-answer-heavy tiny source | incorrect answer or reasoning (33%); low-value, ambiguous, or overly narrow signal (22%) |
| `oliverkinch/tidsskrift-dk-bt` | 64% | 1 | 62,934 | 38,334,152 | retain one pass | instruction or output-format mismatch (32%); truncated or incomplete target (24%) |
| `oliverkinch/eur-lex-bt` | 64% | 1 | 2,657 | 1,669,455 | retain one pass | instruction or output-format mismatch (41%); truncated or incomplete target (15%) |
| `oliverkinch/doab-da-bt` | 68% | 1 | 123 | 69,388 | retain one pass | instruction or output-format mismatch (46%); truncated or incomplete target (24%) |
| `oliverkinch/dynaword-bt` | 70% | 1 | 31,100 | 17,152,501 | retain one pass | instruction or output-format mismatch (35%); truncated or incomplete target (29%) |
| `nvidia/OpenMathInstruct-2` | 68% | 2 | 0 | 0 | repaired replacement | instruction or output-format mismatch (22%); incorrect answer or reasoning (20%) |
| `schneiderkamplab/opus-da-en-permissive` | 75% | 1 | 0 | 0 | repaired replacement | translation mismatch or failure (40%); incorrect answer or reasoning (21%) |
| `facebook/asset` | 75% | 2 | 2,359 | 150,768 | retain one pass | instruction or output-format mismatch (26%); grammar or fluency defect (13%) |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task871-msmarco-question-generation` | 74% | 1 | 0 | 0 | exclude negligible low-quality source | instruction or output-format mismatch (43%); truncated or incomplete target (26%) |
| `oliverkinch/da-instruct-dynaword-contemporary` | 75% | 1 | 0 | 0 | repaired replacement | instruction or output-format mismatch (36%); truncated or incomplete target (29%) |
| `alexandrainst/nordjylland-news-summarization` | 76% | 1 | 0 | 0 | repaired replacement | instruction or output-format mismatch (45%); ungrounded or hallucinated content (17%) |
| `danish-foundation-models/kaenguruen` | 76% | 2 | 212 | 31,889 | retain one pass | incorrect answer or reasoning (16%); instruction or output-format mismatch (9%) |
| `allenai/IF_sft_data_verified` | 76% | 1 | 31,747 | 19,940,266 | retain one pass | instruction or output-format mismatch (39%); incorrect answer or reasoning (11%) |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task264-paper-reviews-accept-reject` | 80% | 1 | 141 | 49,270 | retain one pass | incorrect answer or reasoning (21%); instruction or output-format mismatch (7%) |
| `schneiderkamplab/sapient-synth-flan-dialog-zsopt-data-qrecc` | 77% | 1 | 10,663 | 1,728,299 | retain one pass | ungrounded or hallucinated content (36%); instruction or output-format mismatch (19%) |
| `alexandrainst/multi-zebra-logic` | 76% | 6 | 768 | 521,134 | retain one pass | ungrounded or hallucinated content (29%); incorrect answer or reasoning (15%) |
| `grammarly/coedit` | 79% | 2 | 70,783 | 4,210,935 | retain one pass | instruction or output-format mismatch (25%); grammar or fluency defect (16%) |
| `oliverkinch/eur-lex-sum-instruct` | 75% | 1 | 69 | 262,879 | retain one pass | instruction or output-format mismatch (29%); ungrounded or hallucinated content (17%) |
| `oliverkinch/machine-translation-da-en` | 78% | 1 | 0 | 0 | exclude in favor of filtered OPUS DA-EN | translation mismatch or failure (39%); ungrounded or hallucinated content (18%) |
| `schneiderkamplab/sapient-synth-flan-flan-fsnoopt-data-aeslc-1.0.0` | 78% | 1 | 11,220 | 4,789,274 | retain one pass | instruction or output-format mismatch (24%); truncated or incomplete target (12%) |
| `oliverkinch/da-instruct-dynaword-contemporary-hq` | 78% | 1 | 0 | 0 | repaired replacement | instruction or output-format mismatch (28%); truncated or incomplete target (26%) |
| `allenai/Dolci-Instruct-SFT-Tool-Use` | 75% | 0 | 0 | 0 | repaired replacement | tool-call or agent-trajectory defect (29%); instruction or output-format mismatch (24%) |
| `allenai/tulu-3-sft-personas-algebra` | 77% | 1 | 20,000 | 21,019,876 | retain one pass | instruction or output-format mismatch (26%); truncated or incomplete target (17%) |
| `MegaScience/TextbookReasoning` | 79% | 2 | 1,178,449 | 374,316,487 | retain one pass | instruction or output-format mismatch (20%); truncated or incomplete target (7%) |
| `Muennighoff/natural-instructions` | 79% | 661 | 2,729,950 | 723,722,346 | retain one pass | instruction or output-format mismatch (20%); incorrect answer or reasoning (11%) |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1374-newscomm-translation` | 78% | 1 | 716 | 173,515 | retain one pass | translation mismatch or failure (26%); instruction or output-format mismatch (22%) |
