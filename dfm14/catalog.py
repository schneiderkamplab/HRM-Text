"""Research candidates, not an admission or publication manifest."""

LANGUAGES = dict(ga="Irish", mt="Maltese", mk="Macedonian", eu="Basque",
    gl="Galician", cy="Welsh", ru="Russian", tr="Turkish", zh="Chinese",
    ar="Arabic", ja="Japanese", id="Indonesian", ko="Korean", hi="Hindi",
    vi="Vietnamese", he="Hebrew")


def sources():
    result = []

    def add(repo, languages, kind="instruction", patterns=None, **kwargs):
        result.append(dict(repo=repo, languages=languages, kind=kind,
            patterns=patterns or ["**/*.parquet", "*.parquet", "**/*.jsonl", "*.jsonl",
                                   "**/*.jsonl.gz", "*.jsonl.gz", "**/*.json", "*.json", "*.csv", "*.jsonl.zst"],
            **kwargs))

    for language in LANGUAGES:
        add("CohereLabs/aya_dataset", [language], patterns=["data/train-*.parquet"],
            language_field="language_code", component="aya-" + language)
    for repo, language in [
        ("IlyaGusev/saiga_scored", "ru"),
        ("m-a-p/COIG-CQIA", "zh"), ("arbml/CIDAR", "ar"),
        ("heegyu/open-korean-instructions", "ko"),
        ("HAERAE-HUB/HR-Instruct-Math-v0.1", "ko"),
        ("Viet-Mistral/viet4all", "vi"), ("jmcinern/Dolly-V2-gle", "ga"),
        ("ptrdvn/kakugo-mlt", "mt"), ("ptrdvn/kakugo-cym", "cy"),
        ("MartinV/clement-mk-handwritten", "mk"),
        ("proxectonos/galician-gec-corpora", "gl"),
    ]:
        add(repo, [language])
    add("merve/turkish_instructions", ["tr"], patterns=["instructions.csv"],
        field_mapping={"talimat":"instruction", "giriş":"input", "çıktı":"output"})
    add("tokyotech-llm/Swallow-Instruct-v0.1", ["ja"], patterns=["oasst1-21k-ja-imitation_alpha.jsonl"])
    add("proxectonos/cpt_instruction_datasets", ["gl"], patterns=["gl_*.jsonl"])
    add("BSC-LT/ALIA-2606-SFT", ["eu", "gl"], language_field="lang")
    add("ai4bharat/indic-align", ["hi"], adapter="indic_hindi",
        patterns=["indicalign-instruct/wiki_chat/*.parquet", "indicalign-instruct/dolly/*.parquet"])
    add("indonlp/cendol_collection_v2", ["id"], language_field="language")
    add("BAAI/Infinity-Instruct", ["zh"], language_field="langdetect")
    # Additional independent/native pools plus explicit translated supplements.
    for repo, language in [
        ("IlyaGusev/ru_turbo_alpaca", "ru"), ("Vikhrmodels/GrandMaster-PRO-MAX", "ru"),
        ("TIGER-Lab/MathInstruct", "en"),
        ("halilibr/collected-turkish-instructions-v0.1", "tr"),
        ("bysismo/Turkish-Python-instruction", "tr"),
        ("HiTZ/magpie-en-eu-reasoning-instructions-qwen3", "eu"),
        ("orai-nlp/MagpieEU", "eu"),
        ("BlossomsAI/merged_vietnamese_instruction_dataset", "vi"),
        ("5CD-AI/Vietnamese-OpenHermes-2.5", "vi"),
        ("kunishou/databricks-dolly-15k-ja", "ja"),
        ("llm-jp/ichikara-instruction", "ja"),
        ("FreedomIntelligence/evol-instruct-arabic", "ar"),
        ("FreedomIntelligence/evol-instruct-hindi", "hi"),
        ("FreedomIntelligence/evol-instruct-indonesian", "id"),
        ("FreedomIntelligence/evol-instruct-korean", "ko"),
        ("FreedomIntelligence/evol-instruct-chinese", "zh"),
        ("saillab/alpaca_macedonian_taco", "mk"),
        ("saillab/alpaca_maltese_taco", "mt"),
        ("saillab/alpaca_welsh_taco", "cy"),
    ]:
        add(repo, [language])
    add("BrainboxAI/medical-training-il", ["he"], patterns=["medical_training_il_train.jsonl"],
        language_field="language", allow_source_values=["he-wikipedia"],
        note="Only Hebrew Wikipedia grounding; exclude English exam QA and identity rows")
    # Aya's collection is a fallback, not all human-authored or uncontaminated.
    for language, name in [("he", "hebrew"), ("ga", "irish"), ("mt", "maltese"),
                           ("mk", "macedonian"), ("cy", "welsh")]:
        add("CohereLabs/aya_collection_language_split", [language],
            patterns=[f"{name}/train*.parquet", f"{name}/*.jsonl"], component="aya-collection-" + language)
    for language in LANGUAGES:
        add("wikimedia/wikipedia", [language], "document",
            [f"20231101.{language}/train-*.parquet"], component="wikipedia-" + language)
    add("danish-foundation-models/faroese-dynaword", ["fo"], "document", ["data/logir/data.parquet"])
    add("SlayerLab/polish-dynaword", ["pl"], "document",
        [f"data/{name}/*.parquet" for name in ("openstax_pl", "open_agh_chemistry_pl",
         "edukacja_medialna_pl", "open_icm_pl", "studia_bas", "wiadomosci_statystyczne_pl",
         "kultura_bez_barier_pl")])
    add("MatinaAI/matina_persian_text_corpus", ["fa"], "document",
        ["chap-sch-books.jsonl.gz", "wiki*.jsonl.gz", "*book*.jsonl.gz"])
    add("nvidia/Nemotron-SFT-Science-v2", ["en"])
    add("tokyotech-llm/swallow-math-v2", ["en"], patterns=["stage3-qa/*.jsonl"])
    add("BAAI/IndustryInstruction", ["zh"], language_field="lang")
    for item in result:
        item.setdefault("component", item["repo"].replace("/", "--"))
    from dfm14.instruction_additions import sources as instruction_additions
    result.extend(instruction_additions())
    from dfm14.english_additions import sources as english_additions
    result.extend(english_additions())
    return result


def supplements():
    """Curated document sources, never general web/PDF crawls."""
    result = [dict(repo="wikimedia/wikisource", languages=[language], kind="document",
        patterns=[f"20231201.{language}/train-*.parquet"], component="wikisource-" + language)
        for language in LANGUAGES if language not in {"ga", "mt"}]
    for language, name in [("ga", "irish"), ("mt", "maltese")]:
        result.append(dict(repo="dennlinger/eur-lex-sum", languages=[language], kind="document",
            patterns=[f"data/{name}/train.json"], component="eurlex-train-" + language,
            field_mapping={"reference": "text", "celex_id": "title"},
            max_row_chars=2000000,
            note="Official EU documents, train only; summaries are not training targets."))
    return result


def institutional_sources():
    return [dict(repo="OPUS/EUbookshop", languages=[language], kind="document",
        component="eubookshop-" + language, patterns=["documents.jsonl"],
        url=f"https://object.pouta.csc.fi/OPUS-EUbookshop/v2/xml/{language}.zip",
        note="EU publications, not general web; XML paragraph boundaries retained; audit OCR and historical facts")
        for language in ("ga", "mt")]
