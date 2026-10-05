# Persian Wikipedia Transform Review: 16 Examples

2026-10-03. CPU/read-only inspection; four accepted examples per task from the
four current uploaded Persian Wikipedia transform entries. No model calls,
GPU actions, data/code/registry/eligibility changes. Generated review artifacts
only. Sample selected before semantic reading: published row ordinals
`floor((N-1)*i/3)`, i=0..3 for each task. This is deterministic spread, not random
sampling and not a population quality-rate estimate.

## Result

**Source identity, source-window replay and transform replay pass for all 16.**
No wrong article join, missing shuffled block, invented paragraph, changed target,
or generative assistant-repair hallucination was found. All sampled rows are
original `accepted`, not accepted repairs.

The material concerns are upstream/window/task quality, which exact replay alone
does not validate:

- All four reordering cases contain headings/category metadata as shuffled units.
  Cases 4 and 5 are especially degenerate: empty standalone headings have no
  semantic payload to determine a unique order. Cases 6 and 7 retain real ordering
  cues between two prose blocks, so they are weak tasks, not wholly unsolvable.
- Prefix cases 8 and 11 expose only metadata, without the person's name, then
  supervise detailed category inventories. Case 9 also targets category tail.
  Case 10 has a meaningful prose/list continuation before its metadata tail.
- Denoising case 3 retains an empty birth-date template and duplicated club in
  the supposedly corrected target. Reordering case 6 retains another empty
  birth-date template. These are inherited source defects, not corruption bugs.
- Span case 13 has a visible source chronology contradiction: July 2015 damage,
  months of repairs, then an April 2015 resumption. The exact extracted span is
  still correct. Case 14 has suspect literal Persian wording; this is explicitly
  a native-review uncertainty, not an independently proven biographical error.

No blanket pass/hold rate is assigned. The report does not declare the full
corpus unfit, clear existing holds, or demand unique answers for language modeling.
It supports filtering page furniture and checking source cleanliness before
treating exact-match audit success as evidence of useful task construction.

## Task Fidelity and Solvability

| Task | Mechanical result in these four samples | Semantic reading |
| --- | --- | --- |
| Denoising | Exact original targets; 2, 6, 7, 12 alphabetic deletions restored; no case changes | Mostly recoverable spelling; metadata-heavy, one visibly unclean target |
| Paragraph reordering | Same complete original double-newline blocks, nonidentity permutations, exact original targets | Page furniture inflated paragraph counts; two cases retain useful prose ordering cues |
| Prefix continuation | Exact source suffix after whitespace trimming | Open-ended by design; category-only windows are a separate quality concern |
| Span filling | One gap; exact stripped source spans, lengths 54/352/82/189 characters | Plausible cloze, often knowledge-dependent; source flaws survive |

All four Persian instruction templates are comprehensible and appropriate in
register for direct task commands. `بندها` is understandable as paragraphs;
the problem is what the generator counts as a paragraph, not that instruction's
language. Fine stylistic preference is not treated as an error. Persian fluency
judgments here are limited; obvious structural/template defects are higher
confidence than nuanced translation-quality judgments.

Source fidelity is to the pinned historical article, not a certification of
every fact in it. Prefix/cloze tasks normally have multiple plausible outputs;
nonuniqueness alone is not a construction bug. Conversely, the model cannot see
the source title or full `audit_context.original` unless included in messages:
`scripts/tokenize_chat_template.py` renders messages, not audit metadata. Judges
checking against that hidden original can verify the target without establishing
that the learner-facing task is informative or recoverable.

## Source and Code Binding

Upstream: `wikimedia/wikipedia`, revision
`b04c8d1ceb2f5cd4588862100d08de323dccfbaa`, config `20231101.fa`.
All referenced local parquet file bytes match the preparation receipt.
Article ID/title/URL, file and row match the selected source records.
`window(source_text, window_seed, max_chars=4500)` reproduces each exact
`audit_context.original`; `transform(..., seed=20261003)` reproduces each ID and
both messages. Separate content checks validate deletions, permutations and
prefix/span boundaries. Source paragraph stripping/joining and target edge
whitespace normalization are intentional; do not describe spans as raw-byte
identity across removed boundary whitespace.

| Published task | Rows in pinned publication | HF data revision |
| --- | ---: | --- |
| denoising | 73,802 | 64bf4b8aae08c303734d162e9d0fd736f85914ac |
| paragraph-reordering | 31,490 | 2c931642f524e79942e41b59cb71d6624bba7a60 |
| prefix-continuation | 110,813 | 3d2f4397565d8bd12e329b01e3900fb1de5cb692 |
| span-filling | 25,937 | aeaa6b115e61ecda16a2df4add70b040945c16e8 |

Repos are `schneiderkamplab/dfm13-wave4-wikipedia-fa-<task>`. These are the
registry-pinned publications, not an assertion that remote main was refreshed
during this CPU-only review. Every local published file hash was checked.

Evidence SHA256:
`093d792842302c3dde3ba832954bd1adac786dffe9101d6095b9d1b1b3d45cae`.
`evidence.json` retains full source articles, full published records, source file
pins, publication/revision metadata and code hashes. `mechanical-checks.json`
contains the separate construction checks. `review.json` joins manual findings
with exact candidate/record/window hashes. `receipt.json` binds all report files.

## Per-Case Full Input and Target


### Case 0 / denoising / چین در بازی‌های المپیک تابستانی ۲۰۰۰

ID: `00018418bfdfb87732534dd567e55b1c0db56734c41b7401b5a3a33244133071`

Record SHA256: `f24a759531167db4a564bfe5a32b8cc140ac1fea25a0e6a2576de560f277c1cd`

Source: `20231101.fa/train-00001-of-00004.parquet`, row 50871, article 2057716.

Assessment: **valid_denoising_with_metadata_caveat** (high). Two actual character deletions, both in category lines: خل to خلق and ین to چین. Target is exactly the source window. Recoverable spelling task with repeated China context; main prose remains intact. Category tail adds low-value boilerplate but is not an impossible repair. No factual Olympic-statistics verification claimed.

**Full learner input**

(فارسی) خطاهای متن را اصلاح کن.

چین در بازی‌های المپیک تابستانی ۲۰۰۰ که در شهر سیدنی استرالیا برگزار شد، کاروان چین با ۲۷۱ ورزشکار در این رقابت‌ها شرکت کرد و موفق به کسب ۵۸ مدال (۲۸ طلا، ۱۶ نقره، ۱۴ برنز) شد. در جدول رتبه‌بندی توزیع مدال‌ها، چین در ردهٔ ۳ مسابقات قرار گرفت.

جستارهای وابسته 
 بازی‌های المپیک تابستانی ۲۰۰۰
 جدول مدال‌های بازی‌های المپیک تابستانی ۲۰۰۰
 چین در بازی‌های المپیک

منابع

جمهوری خل چین در بازی‌های المپیک
ین در بازی‌های المپیک تابستانی بر پایه سال
کشورها در المپیک تابستانی ۲۰۰۰
ورزش چین در ۲۰۰۰ (میلادی)

**Full target**

چین در بازی‌های المپیک تابستانی ۲۰۰۰ که در شهر سیدنی استرالیا برگزار شد، کاروان چین با ۲۷۱ ورزشکار در این رقابت‌ها شرکت کرد و موفق به کسب ۵۸ مدال (۲۸ طلا، ۱۶ نقره، ۱۴ برنز) شد. در جدول رتبه‌بندی توزیع مدال‌ها، چین در ردهٔ ۳ مسابقات قرار گرفت.

جستارهای وابسته 
 بازی‌های المپیک تابستانی ۲۰۰۰
 جدول مدال‌های بازی‌های المپیک تابستانی ۲۰۰۰
 چین در بازی‌های المپیک

منابع

جمهوری خلق چین در بازی‌های المپیک
چین در بازی‌های المپیک تابستانی بر پایه سال
کشورها در المپیک تابستانی ۲۰۰۰
ورزش چین در ۲۰۰۰ (میلادی)

**Published audit reason (not independent evidence)**

The model successfully performed the denoising task. It corrected the typos in the 'References' section (changing 'جمهوری خل چین' to 'جمهوری خلق چین' and fixing the broken word 'ین' to 'چین') while preserving the rest of the text accurately.


### Case 1 / denoising / لین اسپیرز

ID: `55f8830e7dfea306a8a2393937506ae7430dd7fffbabf6b918ddcfa7e8c01f22`

Record SHA256: `fa025ea8db2e42fd74d1dbca8af38210eae9023d13ab1372e5b0925c38a40c46`

Source: `20231101.fa/train-00000-of-00004.parquet`, row 99275, article 505954.

Assessment: **valid_denoising_with_metadata_caveat** (high). Six deleted letters restored exactly, including بیتنی to بریتنی and اراد to افراد. Most text is biography categories rather than prose; spelling restoration remains meaningful. The preserved description of a teenage actor is historical source wording, not independently checked current biography. No transformation hallucination.

**Full learner input**

(فارسی) خطاهای متن را اصلاح کن.

لین آیرین اسپیرز  (née Bridges) (متولد ۴ مه ۱۹۵۵) نویسنده و مادر ستاره پاپ بیتنی اسپیرز و بازیگر نوجوان جیمی لین اسپیرز است.

منابع

اراد آمریکایی انگلیسی‌تبار
افراد آمریکایی مالتی‌تبار
افراد زنده
اهالی کنتوود، لوئیزیانا
اهالی مک‌کام، میسیسیپی
باپتیست‌های اهل ایالات متحده آمریکا
بریتنی اسپیرز
دانش‌آموختگان دانشگاه ردینگ
رمان‌نویسان سده ۲۱ (میلادی)
رمان‌نویسان سده ۲۱ (میلادی) اهل ایالات متحده آمریکا
زادگان ۱۹۵۵ (میلادی)
نویسندگان اهل ایالات متحده آمریکا
نویسندگان زن اهل ایالات متحده آمریکا
نویسندگان زن سده ۲۰ (میلادی)
نویسندگان زن سده ۲۰ (میلاد) اهل ایالات متحده آمریکا
نویسندگان زن سده ۲۱ (میلادی) اهل ایالات متحده آمریکا
نویسندگان سده ۲۰ (میلادی) اهل ایالات متحده آمریکا
پیروان کلیسای کاتولیک رم اهل ایالات متحه آمیکا
نوکیشن کلیسای کاتولیک روم

**Full target**

لین آیرین اسپیرز  (née Bridges) (متولد ۴ مه ۱۹۵۵) نویسنده و مادر ستاره پاپ بریتنی اسپیرز و بازیگر نوجوان جیمی لین اسپیرز است.

منابع

افراد آمریکایی انگلیسی‌تبار
افراد آمریکایی مالتی‌تبار
افراد زنده
اهالی کنتوود، لوئیزیانا
اهالی مک‌کام، میسیسیپی
باپتیست‌های اهل ایالات متحده آمریکا
بریتنی اسپیرز
دانش‌آموختگان دانشگاه ردینگ
رمان‌نویسان سده ۲۱ (میلادی)
رمان‌نویسان سده ۲۱ (میلادی) اهل ایالات متحده آمریکا
زادگان ۱۹۵۵ (میلادی)
نویسندگان اهل ایالات متحده آمریکا
نویسندگان زن اهل ایالات متحده آمریکا
نویسندگان زن سده ۲۰ (میلادی)
نویسندگان زن سده ۲۰ (میلادی) اهل ایالات متحده آمریکا
نویسندگان زن سده ۲۱ (میلادی) اهل ایالات متحده آمریکا
نویسندگان سده ۲۰ (میلادی) اهل ایالات متحده آمریکا
پیروان کلیسای کاتولیک رم اهل ایالات متحده آمریکا
نوکیشان کلیسای کاتولیک روم

**Published audit reason (not independent evidence)**

The model successfully performed the denoising task. It corrected several typos in the Persian text: 'بیتنی' to 'بریتنی' (Britney), 'اراد' to 'افراد' (people), 'متحه آمیکا' to 'متحدة آمریکا' (USA), and 'نوکیشن' to 'نوکیشان' (denominations/followers). The output is clean and natural.


### Case 2 / denoising / برایان کلاف

ID: `aaab12c996b1c86f529f3148a84f68920ec4a8d7cfef460d4e87f419e4bd623c`

Record SHA256: `f5cb7b6706b5b636b9c0c276474f2f8f2eefbb61c54b8c0c489a273556599a96`

Source: `20231101.fa/train-00000-of-00004.parquet`, row 200607, article 1273836.

Assessment: **category_only_window_warning** (high). The selected 974-character window is an English-Wikipedia link followed by categories, not Brian Clough's narrative biography. Seven letter deletions are correctly restored, including قهمانان to قهرمانان and برت اگلستان to برتر انگلستان. Mechanically valid and generally recoverable orthography, but poor evidence of substantive prose denoising; arbitrary category inventory is not a coherent article.

**Full learner input**

(فارسی) خطاهای متن را اصلاح کن.

ویکی‌پدیای انگلیسی Brian Clough

افراد در حزب کارگر (بریتانیا)
افسران رتبه امپراتوری بریتانیا
اهالی میدلزبورو
بازیکنان باشگاه ساندرلند
بازیکنان باشگاه میدلزبورو
بازیکنان تیم ملی فوتبال انگلستان
بازیکنان تیم ملی فوتبال ب انگلستان
بازیکنان تیم ملی فوتبال زیر ۲۳ سال انگلستان
بازیکنان فوتبال اهل انگلستان
بازیکنان فوتبال اهل میدلزبورو
بازیکنان فوتبال اهل یور‌شر شمالی
بازیکنان لیگ فوتبال انگلستان
بازیکنان لیگ فوتبال به عنوان عضوی از لیگ XI بریتانیا
براین کلاف
خودزندگی‌نامه‌نویسان اهل انگلستان
درگذشتگان ۲۰۰۴ (میلادی)
درگذشتگان به علت سرطان در انگلستان
درگذشتگان به علت سرطان معده
راه‌یافتگان به تالار مشاهیر فوتبال انگلستان
زاگان ۱۹۳۵ (میلادی)
سوسیالیست‌های اهل انگلستان
کارکان نیروی هوایی سلطنتی سده ۲۰ (میلادی)
مربیان باشگاه فوتبال دربی کانتی
مربیان باشگاه فوتبال لیدز یونایتد
مربیان باشگاه فوتبال ناتینگهام فارست
مربیان باشگاه فوتبال هارتل‌پول یونایتد
مربیان برنده لیگ قهمانان اروپا
مربیان فوتبال اهل انگلستان
مربیان لیگ برت اگلستان
مربیان لیگ فوتبال
مهاجمان فوتبال

**Full target**

ویکی‌پدیای انگلیسی Brian Clough

افراد در حزب کارگر (بریتانیا)
افسران رتبه امپراتوری بریتانیا
اهالی میدلزبورو
بازیکنان باشگاه ساندرلند
بازیکنان باشگاه میدلزبورو
بازیکنان تیم ملی فوتبال انگلستان
بازیکنان تیم ملی فوتبال ب انگلستان
بازیکنان تیم ملی فوتبال زیر ۲۳ سال انگلستان
بازیکنان فوتبال اهل انگلستان
بازیکنان فوتبال اهل میدلزبورو
بازیکنان فوتبال اهل یورک‌شر شمالی
بازیکنان لیگ فوتبال انگلستان
بازیکنان لیگ فوتبال به عنوان عضوی از لیگ XI بریتانیا
برایان کلاف
خودزندگی‌نامه‌نویسان اهل انگلستان
درگذشتگان ۲۰۰۴ (میلادی)
درگذشتگان به علت سرطان در انگلستان
درگذشتگان به علت سرطان معده
راه‌یافتگان به تالار مشاهیر فوتبال انگلستان
زادگان ۱۹۳۵ (میلادی)
سوسیالیست‌های اهل انگلستان
کارکنان نیروی هوایی سلطنتی سده ۲۰ (میلادی)
مربیان باشگاه فوتبال دربی کانتی
مربیان باشگاه فوتبال لیدز یونایتد
مربیان باشگاه فوتبال ناتینگهام فارست
مربیان باشگاه فوتبال هارتل‌پول یونایتد
مربیان برنده لیگ قهرمانان اروپا
مربیان فوتبال اهل انگلستان
مربیان لیگ برتر انگلستان
مربیان لیگ فوتبال
مهاجمان فوتبال

**Published audit reason (not independent evidence)**

The model successfully performed the denoising task. It corrected several typos in the Persian text: 'یور‌شر' to 'یورک‌شر', 'براین کلاف' to 'برایان کلاف', 'زاگان' to 'زادگان', 'کارکان' to 'کارکنان', 'قهمانان' to 'قهرمانان', and 'برت اگلستان' to 'برتر انگلستان'. It also correctly handled the spacing error in 'ب انگلستان'.


### Case 3 / denoising / رافائل مید

ID: `ffff37fa4db904d7c44992cfc28cff97c4e2e4b0db250be0f027daaf0e91bcd9`

Record SHA256: `449e979cdcf19991ed2d45f557c54102ae2fc18a1617649075141eb4328adbf1`

Source: `20231101.fa/train-00002-of-00004.parquet`, row 150897, article 4760439.

Assessment: **inherited_source_defect_in_target** (high). All twelve deletions are faithfully repaired. However, the target retains the visibly empty biographical template رافائل مید (؛ زادهٔ ) and lists Brighton twice. This conflicts with treating the full output as clean error-corrected prose. The defects are already in the source, not introduced by corruption or a generative repair.

**Full learner input**

(فارسی) خطاهای متن را اصلاح کن.

رافائل مید (؛ زادهٔ ) بازیکن فوتبال اهل بریتانیا است.

از باشگاه‌هایی که در آن بازی کرده‌است می‌توان به باشگاه فوتال ایپسویچ تاون، باشگاه فوتبال اسپورتینگ پرتغال، باشگاه فوتبال آرسنال، باشگاه فوتال سیتینگبورو، باشگاه فوتبال کراولی تاون، باشگاه فوتبال داندی یونایتد، باشگاه فتبال لوتون تاون، باشگاه فوتبال رئال بتیس، باشگاه فوتبال پلیموث آرگیل، باشگاه فوتبال برایتون اند هوو آلبیون، و باشگه فوتبال برایتون اند هوو آلبیون، اشاره کرد.

نابع

افراد زنده
اهالی اسلینگتون
بازیکنان باشگاه آرسنال
بازیکنان باشگاه اسپورتینگ پرتغال
بازیکنان باشگاه ایپسویچ تون
بازیکنان باشگاه برایتون و هاو آلبیون
بازیکنان باشگاه پلیموث آرگیل
بازیکنان باشگاه داندی یونایتد
بازیکان باشگاه رئال بتیس
بازیکنان باشگاه کراولی تاون
بازیکنان باشگاه لوتون تاون
بازیکنان فوتبال اهل انگلستان
بازیکنان فوتبال دور از وطن در اسپانیا
بازینان فوتبال دور از وطن در پرتغال
بازیکنان فوتبال دور از وطن در دانمارک
بازیکنان فوتبال دور از وطن در هنگ کنگ
بازیکنان فوتبال لیگ برتر جنوبی
بازیکنان فوتبال مهاجر اهل انگلستان
بازیکنان لا لیگا
بازیکنان لیگ برتر پرتغال
بزیکنان لیگ فوتبال اسکاتلند
بازیکنان لیگ فوتبال انگلستن
دور از وطن‌های اهل بریتانیا در هنگ کنگ
زادگان ۱۹۶۲ (میلادی)
مهاجمان فوتبال
رزکاران دور از وطن اهل انگلستان در اسپانیا
ورزشکاران دور از وطن اهل انگلستان در هنگ کنگ

**Full target**

رافائل مید (؛ زادهٔ ) بازیکن فوتبال اهل بریتانیا است.

از باشگاه‌هایی که در آن بازی کرده‌است می‌توان به باشگاه فوتبال ایپسویچ تاون، باشگاه فوتبال اسپورتینگ پرتغال، باشگاه فوتبال آرسنال، باشگاه فوتبال سیتینگبورو، باشگاه فوتبال کراولی تاون، باشگاه فوتبال داندی یونایتد، باشگاه فوتبال لوتون تاون، باشگاه فوتبال رئال بتیس، باشگاه فوتبال پلیموث آرگیل، باشگاه فوتبال برایتون اند هوو آلبیون، و باشگاه فوتبال برایتون اند هوو آلبیون، اشاره کرد.

منابع

افراد زنده
اهالی اسلینگتون
بازیکنان باشگاه آرسنال
بازیکنان باشگاه اسپورتینگ پرتغال
بازیکنان باشگاه ایپسویچ تاون
بازیکنان باشگاه برایتون و هاو آلبیون
بازیکنان باشگاه پلیموث آرگیل
بازیکنان باشگاه داندی یونایتد
بازیکنان باشگاه رئال بتیس
بازیکنان باشگاه کراولی تاون
بازیکنان باشگاه لوتون تاون
بازیکنان فوتبال اهل انگلستان
بازیکنان فوتبال دور از وطن در اسپانیا
بازیکنان فوتبال دور از وطن در پرتغال
بازیکنان فوتبال دور از وطن در دانمارک
بازیکنان فوتبال دور از وطن در هنگ کنگ
بازیکنان فوتبال لیگ برتر جنوبی
بازیکنان فوتبال مهاجر اهل انگلستان
بازیکنان لا لیگا
بازیکنان لیگ برتر پرتغال
بازیکنان لیگ فوتبال اسکاتلند
بازیکنان لیگ فوتبال انگلستان
دور از وطن‌های اهل بریتانیا در هنگ کنگ
زادگان ۱۹۶۲ (میلادی)
مهاجمان فوتبال
ورزشکاران دور از وطن اهل انگلستان در اسپانیا
ورزشکاران دور از وطن اهل انگلستان در هنگ کنگ

**Published audit reason (not independent evidence)**

The model successfully performed the denoising task in Persian. It corrected several typos in the list of categories (e.g., 'بازیکان' to 'بازیکنان', 'بزیکنان' to 'بازیکنان', 'انگلستن' to 'انگلستان', 'رزکاران' to 'ورزشکاران') and standardized the club names (e.g., 'فوتال' to 'فوتبال'). It also fixed the header 'نابع' to 'منابع' (Sources), which was clearly a typo in the source text. The output is clean and follows the natural structure of a Wikipedia entry.


### Case 4 / paragraph-reordering / کاسیا اسموتنیاک

ID: `0001679498f2753f9864eac03d4f75e30c6a4abf071de6316eeb479b1776aef2`

Record SHA256: `fefa534e862483e04a7827e9cfa13fa06f3ecb9b36d10a25d6b61267212efec5`

Source: `20231101.fa/train-00001-of-00004.parquet`, row 201496, article 3481192.

Assessment: **degenerate_paragraph_units** (high). Four shuffled blocks consist of one actual filmography paragraph, the empty headings منابع and پیوند به بیرون, and a category-list block. No paragraphs are invented or lost, but calling these four prose paragraphs is misleading. The intended order largely relies on Wikipedia layout conventions; the relative order of empty heading blocks is not uniquely established by semantic content. Window starts after the subject introduction.

**Full learner input**

(فارسی) ترتیب اصلی بندها را بازسازی کن؛ متن کامل را بدون شماره‌گذاری بنویس.

[1] منابع

[2] پیوند به بیرون

[3] افراد زنده
بازیگران زن اهل ایتالیا
برندگان جایزه انجمن ملی فیلم ایتالیا
دور از وطن‌های اهل لهستان در ایتالیا
زادگان ۱۹۷۹ (میلادی)
مانکن‌های زن اهل ایتالیا
بازیگران زن سده ۲۱ (میلادی) اهل ایتالیا
بازیگران زن اهل لهستان
مانکن‌های زن اهل لهستان

[4] از فیلم‌ها یا برنامه‌های تلویزیونی که وی در آن نقش داشته‌است، می‌توان به بارباروسا، از پاریس با عشق، غریبه‌های تمام‌عیار، تحت درمان، کارنرا: کوه متحرک و بوکاچیوی شگفت‌انگیز اشاره کرد. اسموتنیاک در سال ۲۰۱۴ برنده جایزه انجمن ملی فیلم ایتالیا بهترین بازیگر زن شده‌است.

**Full target**

از فیلم‌ها یا برنامه‌های تلویزیونی که وی در آن نقش داشته‌است، می‌توان به بارباروسا، از پاریس با عشق، غریبه‌های تمام‌عیار، تحت درمان، کارنرا: کوه متحرک و بوکاچیوی شگفت‌انگیز اشاره کرد. اسموتنیاک در سال ۲۰۱۴ برنده جایزه انجمن ملی فیلم ایتالیا بهترین بازیگر زن شده‌است.

منابع

پیوند به بیرون

افراد زنده
بازیگران زن اهل ایتالیا
برندگان جایزه انجمن ملی فیلم ایتالیا
دور از وطن‌های اهل لهستان در ایتالیا
زادگان ۱۹۷۹ (میلادی)
مانکن‌های زن اهل ایتالیا
بازیگران زن سده ۲۱ (میلادی) اهل ایتالیا
بازیگران زن اهل لهستان
مانکن‌های زن اهل لهستان

**Published audit reason (not independent evidence)**

The model correctly reordered the scrambled Wikipedia paragraphs into a logical sequence (biography/filmography followed by references and categories) and followed the negative constraint of not including numbering.


### Case 5 / paragraph-reordering / فهرست میراث جهانی در ایسلند

ID: `54f7cdf7abf528ee794ded2fe6f9697eee0fd46ac45bc4acd69636016582077a`

Record SHA256: `e131b68862f00810c025c75df26c85092f5b5eee1573731036b2aca1e878c400`

Source: `20231101.fa/train-00003-of-00004.parquet`, row 109243, article 5852270.

Assessment: **degenerate_paragraph_units** (high). Nine blocks include three prose-bearing blocks, five standalone heading/link blocks (geography, glossary, references, external links, and a UNESCO/Iceland link label), plus categories. The 9-block permutation is exact. Empty headings have no attached payload, so several semantically plausible placements cannot be disambiguated from the learner prompt. Source also retains malformed punctuation باشد.،. This is article-layout reconstruction, not a clean nine-paragraph discourse-order problem.

**Full learner input**

(فارسی) ترتیب اصلی بندها را بازسازی کن؛ متن کامل را بدون شماره‌گذاری بنویس.

[1] واژه‌نامه

[2] میراث جهانی یونسکو در ایسلند

[3] پیوند به بیرون

[4] منابع

[5] افزون بر میراث‌های ثبت شده، ایسلند شش موقعیت دیگر را در فهرست آزمایشی خود گنجانده‌است. سایت موجود در دینگوتیلر دو بار به فهرست آزمایشی افزوده شده؛ یک بار با این پیشنهاد که از اثری فرهنگی به اثری طبیعی و فرهنگی گسترش یابد و بار دیگر به عنوان نامزدی برای بخشی از اثری فرا ملی در میراث پوشش وایکینگ‌ها.

[6] موقعیت جغرافیایی

[7] اروپای شمالی
ایسلند
فهرست‌های جاذبه‌های گردشگری در ایسلند
میراث جهانی
مناطق حفاظت‌شده ایسلند

[8] فهرست آزمایشی 
علاوه بر مکان‌هایی که در فهرست میراث جهانی ثبت شده‌اند، کشورهای عضو می‌توانند فهرستی از مکان‌های آزمایشی را که ممکن است برای نامزدی در نظر گرفته شوند، ارائه کنند. نامزدهای فهرست میراث جهانی تنها در صورتی پذیرفته می‌شوند که سایت قبلاً در فهرست آزمایشی ثبت شده باشد.، ایسلند شش گزینه آزمایشی ارائه کرده‌است.

[9] سایت‌های میراث جهانی 
یونسکو سایت‌ها را با ده معیار فهرست می‌کند. هر ورودی باید حداقل یکی از معیارها را داشته باشد.

**Full target**

افزون بر میراث‌های ثبت شده، ایسلند شش موقعیت دیگر را در فهرست آزمایشی خود گنجانده‌است. سایت موجود در دینگوتیلر دو بار به فهرست آزمایشی افزوده شده؛ یک بار با این پیشنهاد که از اثری فرهنگی به اثری طبیعی و فرهنگی گسترش یابد و بار دیگر به عنوان نامزدی برای بخشی از اثری فرا ملی در میراث پوشش وایکینگ‌ها.

سایت‌های میراث جهانی 
یونسکو سایت‌ها را با ده معیار فهرست می‌کند. هر ورودی باید حداقل یکی از معیارها را داشته باشد.

فهرست آزمایشی 
علاوه بر مکان‌هایی که در فهرست میراث جهانی ثبت شده‌اند، کشورهای عضو می‌توانند فهرستی از مکان‌های آزمایشی را که ممکن است برای نامزدی در نظر گرفته شوند، ارائه کنند. نامزدهای فهرست میراث جهانی تنها در صورتی پذیرفته می‌شوند که سایت قبلاً در فهرست آزمایشی ثبت شده باشد.، ایسلند شش گزینه آزمایشی ارائه کرده‌است.

موقعیت جغرافیایی

واژه‌نامه

منابع

پیوند به بیرون

میراث جهانی یونسکو در ایسلند

اروپای شمالی
ایسلند
فهرست‌های جاذبه‌های گردشگری در ایسلند
میراث جهانی
مناطق حفاظت‌شده ایسلند

**Published audit reason (not independent evidence)**

The model correctly reordered the paragraphs according to the logical structure of a Wikipedia article (content followed by metadata/navigation links) and followed the negative constraint of not using numbering. The Persian language is natural and the task compliance is perfect.


### Case 6 / paragraph-reordering / خوان پوودانو

ID: `ab2af67765a4f7ce3d66d5f7257d1214d26a71791eec016275960f2056d37e54`

Record SHA256: `11f5a270c67ac6c75e1cde6771f161aba1579bcf6f559167171e03ada0a888b6`

Source: `20231101.fa/train-00003-of-00004.parquet`, row 137499, article 5952896.

Assessment: **limited_reordering_with_source_defect** (high). Two real prose blocks (introduction and clubs) plus an empty reference heading and categories. Input order swaps only the two prose blocks; introduction-before-career is a genuine recoverable cue, so do not call it wholly unsolvable. Still fewer than three prose paragraphs, and target retains the empty birth-date parenthesis خوان پوودانو (؛ زادهٔ ). Exact block/target fidelity holds.

**Full learner input**

(فارسی) ترتیب اصلی بندها را بازسازی کن؛ متن کامل را بدون شماره‌گذاری بنویس.

[1] از باشگاه‌هایی که در آن بازی کرده‌است می‌توان به باشگاه فوتبال لگانس، باشگاه فوتبال پومفرادینا، و باشگاه فوتبال اتلتیکو مادرید بی اشاره کرد.

[2] خوان پوودانو (؛ زادهٔ ) بازیکن فوتبال اهل اسپانیا است.

[3] منابع

[4] افراد زنده
بازیکنان باشگاه اتلتیکو مادرید بی
بازیکنان باشگاه فوتبال پومفرادینا
بازیکنان باشگاه لگانیس
بازیکنان سگوندا دیویژن بی
بازیکنان فوتبال اهل اسپانیا
بازیکنان فوتبال دور از وطن در ایسلند
بازیکنان فوتبال مهاجر اهل اسپانیا
بازیکنان لیگ دسته سوم فوتبال اسپانیا
بازیکنان لیگا ادلانته
زادگان ۱۹۷۹ (میلادی)
مدافعان فوتبال

**Full target**

خوان پوودانو (؛ زادهٔ ) بازیکن فوتبال اهل اسپانیا است.

از باشگاه‌هایی که در آن بازی کرده‌است می‌توان به باشگاه فوتبال لگانس، باشگاه فوتبال پومفرادینا، و باشگاه فوتبال اتلتیکو مادرید بی اشاره کرد.

منابع

افراد زنده
بازیکنان باشگاه اتلتیکو مادرید بی
بازیکنان باشگاه فوتبال پومفرادینا
بازیکنان باشگاه لگانیس
بازیکنان سگوندا دیویژن بی
بازیکنان فوتبال اهل اسپانیا
بازیکنان فوتبال دور از وطن در ایسلند
بازیکنان فوتبال مهاجر اهل اسپانیا
بازیکنان لیگ دسته سوم فوتبال اسپانیا
بازیکنان لیگا ادلانته
زادگان ۱۹۷۹ (میلادی)
مدافعان فوتبال

**Published audit reason (not independent evidence)**

The model correctly reordered the scrambled paragraphs into a logical biographical structure (Introduction -> Career -> References/Categories) and followed the negative constraint of not including numbering. The Persian language usage is natural and accurate.


### Case 7 / paragraph-reordering / ساموئل موتوسامی

ID: `ffff5fe0914e0c09b476209407128c5510a6f15bb017ab839ac91b0ee6b7d4c0`

Record SHA256: `8162d7a7ed70c766d72435a18c0e3eed4a5bb0c3cdf9768257b0fba3b09d67dc`

Source: `20231101.fa/train-00003-of-00004.parquet`, row 158073, article 5981483.

Assessment: **limited_reordering_with_context_loss** (high). Two career sentences as separate source paragraphs plus reference heading and categories. همچنین (also) supplies a real cue for club then national-team ordering; transformation is not wholly arbitrary. But the selected window drops the introduction/name, leaving وی without its named antecedent. Most bytes are category metadata and the task is not rich paragraph-order reasoning. Exact source boundaries are preserved; no sentence-splitting invention.

**Full learner input**

(فارسی) ترتیب اصلی بندها را بازسازی کن؛ متن کامل را بدون شماره‌گذاری بنویس.

[1] افراد زنده
افراد فرانسوی جمهوری دموکراتیک کنگویی‌تبار
افراد فرانسوی گوادلوپی‌تبار
بازیکنان باشگاه فوتبال فورتونا سیتارد
بازیکنان باشگاه نانت
بازیکنان تیم ملی فوتبال جمهوری دموکراتیک کنگو
بازیکنان فوتبال اهل پاریس
بازیکنان فوتبال اهل جمهوری دموکراتیک کنگو
بازیکنان فوتبال اهل فرانسه
بازیکنان فوتبال دور از وطن اهل جمهوری دموکراتیک کنگو
بازیکنان فوتبال دور از وطن در هلند
بازیکنان لیگ ۱ فوتبال فرانسه
زادگان ۱۹۹۶ (میلادی)
هافبک‌های فوتبال
ورزشکاران سیاه‌پوست اهل فرانسه
بازیکنان لیگ برتر فوتبال هلند
بازیکنان فوتبال مهاجر اهل فرانسه
افراد فرانسوی هندی‌تبار
بازیکنان باشگاه المپیک لیون

[2] منابع

[3] از باشگاه‌هایی که در آن بازی کرده‌است می‌توان به باشگاه فوتبال المپیک لیون اشاره کرد.

[4] وی همچنین در تیم ملی فوتبال جمهوری دموکراتیک کنگو بازی کرده‌است.

**Full target**

از باشگاه‌هایی که در آن بازی کرده‌است می‌توان به باشگاه فوتبال المپیک لیون اشاره کرد.

وی همچنین در تیم ملی فوتبال جمهوری دموکراتیک کنگو بازی کرده‌است.

منابع

افراد زنده
افراد فرانسوی جمهوری دموکراتیک کنگویی‌تبار
افراد فرانسوی گوادلوپی‌تبار
بازیکنان باشگاه فوتبال فورتونا سیتارد
بازیکنان باشگاه نانت
بازیکنان تیم ملی فوتبال جمهوری دموکراتیک کنگو
بازیکنان فوتبال اهل پاریس
بازیکنان فوتبال اهل جمهوری دموکراتیک کنگو
بازیکنان فوتبال اهل فرانسه
بازیکنان فوتبال دور از وطن اهل جمهوری دموکراتیک کنگو
بازیکنان فوتبال دور از وطن در هلند
بازیکنان لیگ ۱ فوتبال فرانسه
زادگان ۱۹۹۶ (میلادی)
هافبک‌های فوتبال
ورزشکاران سیاه‌پوست اهل فرانسه
بازیکنان لیگ برتر فوتبال هلند
بازیکنان فوتبال مهاجر اهل فرانسه
افراد فرانسوی هندی‌تبار
بازیکنان باشگاه المپیک لیون

**Published audit reason (not independent evidence)**

The model correctly reordered the scrambled Wikipedia paragraphs into a logical biographical structure (biography -> references -> categories) and followed the negative constraint of not using numbering.


### Case 8 / prefix-continuation / ایمن المثلوثی

ID: `0001f278a04e3be26278550e8cce66df6742362ff93e19f35e5ef8ec2f52e8c8`

Record SHA256: `afd49e6701a453b16585df7b614377ecc5e25116534ef6fe8668dc929024f351`

Source: `20231101.fa/train-00002-of-00004.parquet`, row 96560, article 4405215.

Assessment: **category_only_continuation_warning** (high). Entire input and target are category-list fragments; the player name is absent from the model-visible prompt. The target adds exact later tournament appearances, birth year and other classifications. This is a faithful corpus suffix but not an evidence-determined factual reconstruction. Generic continuation is inherently nonunique and that alone is not a bug; the concrete issue is the category-only window and lost subject, not wrong target extraction.

**Full learner input**

(فارسی) متن را ادامه بده؛ فقط ادامهٔ حذف‌شده را بنویس.

افراد زنده
بازیکنان باشگاه آفریقایی
بازیکنان باشگاه الباطن
بازیکنان باشگاه العداله
بازیکنان باشگاه ستاره ساحلی
بازیکنان باشگاه موهان باگان
بازیکنان تیم ملی فوتبال تونس
بازیکنان جام جهانی فوتبال ۲۰۱۸
بازیکنان جام جهانی فوتبال ۲۰۲۲
بازیکنان جام ملت‌های آفریقا ۲۰۰۸
بازیکنان جام ملت‌های آفریقا ۲۰۱۰
بازیکنان جام ملت‌های آفریقا ۲۰۱۲
بازیکنان جام ملت‌های آفریقا ۲۰۱۳ (میلادی)

**Full target**

بازیکنان جام ملت‌های آفریقا ۲۰۱۵
بازیکنان جام ملت‌های آفریقا ۲۰۱۷
بازیکنان رقابت‌های ملت‌های آفریقا ۲۰۱۱
بازیکنان فوتبال اهل تونس
بازیکنان فوتبال دور از وطن اهل تونس
بازیکنان فوتبال دور از وطن در عربستان سعودی
بازیکنان فوتبال دور از وطن در هند
بازیکنان لیگ حرفه‌ای فوتبال عربستان
بازیکنان لیگ دسته اول فوتبال تونس
دروازه‌بانان فوتبال
دور از وطن‌های اهل تونس در عربستان سعودی
زادگان ۱۹۸۴ (میلادی)
ورزشکاران اهل شهر تونس

**Published audit reason (not independent evidence)**

The model correctly follows the prefix-continuation task. It provides the missing list items from the Wikipedia category structure in Persian, maintaining the exact format and style requested without adding unnecessary explanations.


### Case 9 / prefix-continuation / فیلیپ والهاوس چتوود، اولین بارون چتوود

ID: `563530ef33c509e04b98d8c17c934510734996a21a28a26522dd2cbc1fbc3f2a`

Record SHA256: `faab821a3019082488ee51afe9cff3b275d26784796ddb6c9ee45813cb94a655`

Source: `20231101.fa/train-00003-of-00004.parquet`, row 126939, article 5924350.

Assessment: **category_tail_and_source_template_warning** (high). Prefix includes short biography, an empty death-date field, references/external-link headings, then اعضای. Target completes that category phrase and reproduces the remaining category inventory. Exact suffix extraction; a plausible local word continuation exists, but the entire original category list is not recoverable uniquely. Source-template defect and metadata-heavy target, not fabricated output.

**Full learner input**

(فارسی) متن را ادامه بده؛ فقط ادامهٔ حذف‌شده را بنویس.

فیلیپ والهاوس چتوود، اولین بارون چتوود (؛ ۲۱ سپتامبر ۱۸۶۹ – ) فرد نظامی و سیاست‌مدار اهل بریتانیا بود. وی همچنین برندهٔ جوایزی همچون نشان حمام و نشان مریت شده‌است.

منابع

پیوند به بیرون

اعضای

**Full target**

نشان شایستگی
افسران پیاده‌نظام سبک در آکسفوردشر و باکینگهام‌شر
اهالی وست‌مینستر
بارون‌های اعیان پادشاهی متحده
دانش‌آموختگان کالج ایتن
درگذشتگان ۱۹۵۰ (میلادی)
روسای انجمن سلطنتی جغرافیا
زادگان ۱۸۶۹ (میلادی)
شوالیه‌های صلیب بزرگ نشان حمام
شوالیه‌های فرمانده نشان سنت میکائیل و سنت جرج
فرماندهان لژیون دونور
فیلدهای مارشال اهل بریتانیا
نظامیان اهل بریتانیا در جنگ بوئر دوم

**Published audit reason (not independent evidence)**

The model correctly followed the prefix-continuation task. It provided only the missing text starting from 'نشان شایستگی' and accurately reconstructed the Wikipedia list of categories/members in Persian, matching the reference text perfectly.


### Case 10 / prefix-continuation / اطلاع‌یابی

ID: `ab3f5a42a2ffc5c86e9b6ec9bccaac29e6f1e4344d133e72e3430373df7c6be3`

Record SHA256: `11c92e9ee33bd51f43b730a9403ad4a61c8eb972cc19d37b92e9791c80157377`

Source: `20231101.fa/train-00000-of-00004.parquet`, row 87467, article 434218.

Assessment: **coherent_prose_continuation_with_tail_warning** (medium). A meaningful information-literacy discussion and enumerated skills precede the cut; target begins by completing the note-taking phrase and continues the next listed skill. This is a legitimate open-ended language-model continuation target, though exact wording is not deductively determined. It eventually drifts into gallery/related-links/references/categories, weakening density. Some spacing/orthographic conventions are uneven; no confidently material Persian-language defect identified.

**Full learner input**

(فارسی) متن را ادامه بده؛ فقط ادامهٔ حذف‌شده را بنویس.

بخشی از پژوهش‌های علوم کتابداری و اطلاع‌رسانی به کار اطلاع‌یابی شاغلان در حوزه‌های مختلف کار حرفه‌ای متمرکز است. این مطالعات برای بررسی رفتار اطلاع‌یابی کتابدارها، دانشگاهیان، متخصصان پزشکی، مهندسان و حقوق‌دانان انجام می‌شود.

مهارتهای اطلاع یابی 
یان مال لی، مهارتهای اطلاع یابی را شامل مهارتهای بازیابی، ارزیابی، سازماندهی و تبادل اطلاعات می‌داند.
الف) مهارتهای بازیابی: شناخت منابع اطلاعاتی، مهارت در استراتژیهای جستجو و توان استفاده از نمایه نامه‌ها و چکیده نامه‌ها
ب) مهارتهای ارزیابی: دانش انتخاب و ارزیابی اطلاعات، مهارت در استراتژی اطلاعات
ج) مهارتهای سازماندهی: مهارت در یادداشت برداری از

**Full target**

کتابها و نشریات، مهارت در ذخیره‌سازی فردی اطلاعات
د) مهارتهای تبادل اطلاعات: توانایی علمی نویسی

به مجموعه این مهارتها سواد اطلاعاتی می‌گویند از دیدگاه کمیته سواد اطلاعاتی انجمن کتابداران ایالات متحده؛ سواد اطلاعاتی شامل توانایی تشخیص نیاز اطلاعاتی، توانایی جایابی، دسترسی، ارزیابی و استفاده مؤثر از اطلاعات مورد نیاز می‌باشد.

نگارخانه

جستارهای وابسته 
 رفتار اطلاع‌یابی
 مهارت‌های اطلاع‌یابی

منابع 
 ویکی‌پدیای انگلیسی، برداشت شده در ۳ خرداد ۱۳۸۹.
 فاطمه نویدی، اطلاع یابی و بررسی رفتار اطلاع یابی در محیط‌های جدید جستجو، نما: مجله الکترونیکی پژوهشگاه اطلاعات و مدارک علمی ایران، در دسترس در ویستا

اطلاع‌یابی
علم اطلاعات

**Published audit reason (not independent evidence)**

The model correctly completed the prefix task by providing the exact continuation from the reference text. It followed the negative constraint to only write the missing part (though it included the subsequent sections of the Wikipedia entry, which is expected in a prefix-continuation task to maintain context/structure) and maintained the formal Persian language and formatting.


### Case 11 / prefix-continuation / ماکسیم بومونت

ID: `ffff7c4a541b6cd172dd2bff49e6e324ef5f2a11f8c2636602a63ca1bdc57312`

Record SHA256: `8d8ad3e0104fdfb77c48408a0ee3e243de7791d7b2f91b75fef82fd3b048212a`

Source: `20231101.fa/train-00002-of-00004.parquet`, row 228625, article 5244012.

Assessment: **category_only_continuation_warning** (high). Prompt begins with an empty external-links heading and generic living-person/French medalist categories; Maxime Beaumont's name is absent. Target supplies birth year and detailed canoe-event categories. Exact source suffix, not assistant invention, but inadequate evidence to recover this exact unnamed person's metadata. Not a substantive natural prose continuation.

**Full learner input**

(فارسی) متن را ادامه بده؛ فقط ادامهٔ حذف‌شده را بنویس.

پیوند به بیرون

افراد زنده
اهالی بولونی سور مر
برندگان مدال نقره المپیک اهل فرانسه
برندگان مدال‌های بازی‌های المپیک تابستانی ۲۰۱۶

**Full target**

زادگان ۱۹۸۲ (میلادی)
شرکت‌کنندگان بازی‌های مدیترانه ۲۰۱۸
قایقرانان کانو بازی‌های المپیک فرانسه
قایقرانان کانو در بازی‌های اروپایی ۲۰۱۵
قایقرانان کانو در بازی‌های المپیک تابستانی ۲۰۱۲
قایقرانان کانو در بازی‌های المپیک تابستانی ۲۰۱۶
قایقرانان کانو مرد اهل فرانسه
مدال‌آوران المپیک در قایق‌رانی
مدال‌آوران بازی‌های اروپایی در قایقرانی کانو
مدال‌آوران برنز بازی‌های مدیترانه برای فرانسه
قایقرانان کانو در بازی‌های المپیک تابستانی ۲۰۲۰

**Published audit reason (not independent evidence)**

The model correctly followed the prefix-continuation task. It provided only the missing text from the Wikipedia category list in Persian, maintaining the correct formatting and semantic relevance to the subject (Maxime Beaumont).


### Case 12 / span-filling / دعای سمات

ID: `0007484c2c5e29d0abf5b19c479223fa6e995c4944b8a93db1cea3594ccd1023`

Record SHA256: `15a90ebb0a39e116d4b828489ecc791b64e7739715a8a86ac8590112873e0abd`

Source: `20231101.fa/train-00003-of-00004.parquet`, row 17502, article 5442161.

Assessment: **valid_but_knowledge_dependent_cloze** (medium). One exact 54-character source span completes the book title زاد المعاد and a chain-of-transmission clause naming Muhammad ibn Uthman. Grammar and adjoining context support the shape of the gap, but the particular name/full chain require source knowledge and are not uniquely implied. Acceptable cloze construction, not a self-contained factual puzzle. Religious/historical truth not independently certified; metadata tail remains.

**Full learner input**

(فارسی) جای <GAP> را پر کن؛ فقط متن حذف‌شده را بنویس.

در باب سندیت دعای سمات می‌توان اشاره کرد به ذکر این دعا توسط شیخ طوسی در مصباح المتهجد، ابن طاووس در جمال الاسبوع، کفعمی در البلد الامین و مصباح، مجلسی در بحارالانوار و زاد <GAP> حجت بن الحسن است و با واسطه از امام ششم شیعه ابوعبدالله جعفر بن محمد صادق و وی از پدرش محمد باقر نقل گردیده‌است. سید بن طاووس در کتاب جمال الاسبوع دعای سمات را از سه طریقه نقل می‌نماید. این دعا در (مفاتیح الجنان) عباس قمی آورده‌است که به نقل از مصباح شیخ طوسی می‌باشد.

جستارهای وابسته

دعای کمیل
 دعای توسل
 دعای ندبه
 دعای عهد
 دعای مجیر
 دعای جوشن کبیر
 دعای جوشن صغیر

منابع

اصطلاحات اسلامی
محمد باقر
دعاهای شیعه دوازده‌امامی
تشیع

**Full target**

المعاد با سندهایی از محمد بن عثمان عمری که از نواب خاص

**Published audit reason (not independent evidence)**

The assistant correctly identified and filled the gap with the missing text from the source Wikipedia article. The response follows the instruction to provide only the missing text and is factually accurate according to the provided context.


### Case 13 / span-filling / سولار ایمپالس

ID: `550fc28d1fc4a1f22190a44d6e24fae688b076495f8819fcbda6ad8eda2f9529`

Record SHA256: `a93c5793f4813df12911f72f8f849353076acd5ed36135f4e201668a54ba5273`

Source: `20231101.fa/train-00001-of-00004.parquet`, row 175209, article 3282074.

Assessment: **inherited_context_contradiction_and_long_gap** (high_for_chronology). The 352-character target is exactly the removed source span, beginning mid-heading and ending before رشته‌های متفاوت. There is no extraneous assistant prefix despite the judge's suggestion. Visible source context says July 2015 battery damage took months to repair, then says the trip resumed in April 2015: an internal chronology contradiction, independent of external historical lookup. Large omitted project/team narrative requires external knowledge, not unique local recovery. No transformation drift.

**Full learner input**

(فارسی) جای <GAP> را پر کن؛ فقط متن حذف‌شده را بنویس.

این هواپیماها از نوع تک صندلی هستند و نیروی آن‌ها با سلول‌های خورشیدی فتوولتائیک تأمین می‌شود. آن‌ها می‌توانند با همین نیرو از زمین بلند شوند. نمونه‌ای که سولار ایمپالس ۱ نامیده می‌شود به این منظور طراحی شد که تا ۳۶ ساعت در هوا باقی بماند. این هواپیما نخستین پرواز آزمایشی خود را در دسامبر ۲۰۰۹ انجام داد. در ژوئیه ۲۰۱۰ این هواپیما یک پرواز ۲۴ ساعته کامل شامل نه ساعت پرواز شبانه را انجام داد. پیکار و بورشبرگ پروازهای موفقی را با انرژی خورشیدی از سوئیس تا اسپانیا و سپس تا مراکش در سال ۲۰۱۲ به انجام رساندند و در سال ۲۰۱۳ یک پرواز چند مرحله‌ای را از یک سوی ایالات متحده به سوی دیگر آن انجام دادند.

در هواپیمای دوم که در سال ۲۰۱۴ تکمیل شد و سولار ایمپالس ۲ نامیده شد بهبودهایی ایجاد شده و از جمله سلول‌های خورشیدی بیشتر و موتورهای قوی‌تری دارد. در ۹ مارس ۲۰۱۵ پیکار و بورشبرگ سفر به دور زمین با سولار ایمپالس ۲ را با عزیمت از ابو ظبی در امارات متحده عربی آغاز کردند. برنامه این بود که هواپیما پس از یک مسافرت چند مرحله‌ای به دور زمین در اوت ۲۰۱۵ به ابوظبی برگردد. در ژوئن ۲۰۱۵ هواپیما آسیا را طی کرد و در ژوئیه ۲۰۱۵ طولانی‌ترین قسمت سفر خود از ژاپن تا هاوایی را تکمیل کرد. در طول این قسمت از سفر باتری‌های هواپیما آسیب حرارتی دیدند که تعمیر آن‌ها ماه‌ها به طول انجامید. سولار ایمپالس ۲ مسافرت به دور دنیا را در آوریل ۲۰۱۵ از سر گرفت و به کالیفرنیا پرواز کرد. هواپیما مسافرت را تا آنسوی ایالات متحده ادامه داد و در ژوئن ۲۰۱۶ به نیویورک رسید. سپس در همین ماه از اقیانوس اطلس گذشت و به اسپانیا رسید. هواپیما پس از یک توقف در مصر در ۲۶ جولای ۲۰۱۶، ۱۶ ماه پس از ترک ابوظبی و طی حدود ۴۲٫۰۰۰ کیلومتر به این شهر بازگشت.

توسعه پروژه و <GAP> رشته‌های متفاوت را از شش کشور جمع کرده بودند که از ۱۰۰ مشاور بیرونی و ۸۰ شریک تکنولوژیک کمک می‌گرفتند.

پشتیبانی مالی این پروژه توسط چند فرد و شرکت خصوصی و نیز دریافت حدود ۶ میلیون فرانک سوئیس (۶٫۴ میلیون دلار آمریکا) از دولت سوئیس انجام می‌گیرد. تأمین کنندگاه مالی خصوصی پروژه شرکت‌های امگا اس آ، سولوی، اشنیدلر، ABB و آقای Peter Diamandis هستند. EPFL، آژانس فضایی اروپا و گروه شرکت‌های داسو دانش فنی و شرکت سان پاور سلول‌های فتوولتائیک پروژه را فراهم کرده‌اند.
پیکارد اعلام کرد کل پروژه از ابتدای آن در سال ۲۰۰۳ تا اواسط ۲۰۱۵ حدود ۱۵۰ میلیون یورو هزینه داشته‌است. در اواخر ۲۰۱۵ او ۲۰ میلیون یوروی دیگر برای ادامه پرواز دور دنیا کمک جمع کرد.

جدول زمانی 
 ۲۰۰۳: مطالعات امکان‌سنجی در مؤسسه پلی تکنیک فدرال لوزان
 ۲۰۰۴–۲۰۰۵: توسعه مفهوم
 ۲۰۰۶: شبیه‌سازی پروازهای طولانی
 ۲۰۰۶–۲۰۰۹: ساخت نخستین نمونه (HB-SIA؛ سولار ایمپالس ۱)
 ۲۰۰۹: نخستین پرواز سولار ایمپالس ۱
 ۲۰۰۹–۲۰۱۱: پروازهای آزمایشی با سرنشین
 ۲۰۱۱–۲۰۱۲: پروازهای آزمایشی بیشتر در اروپا و شمال آفریقا
 ۲۰۱۱–۲۰۱۳: ساخت دومین نمونه (HB-SIB؛ سولار ایمپالس ۲)
 ۲۰۱۳: پرواز قاره‌ای روی ایالات متحده با سولار ایمپالس ۱
 ۲۰۱۴: نخستین پرواز سولار ایمپالس ۲
 ۲۰۱۵–۲۰۱۶: سفر به دور زمین با سولار ایمپالس ۲، انجام شده در ۱۷ مرحله در ۱۶٫۵ ماه

جستارهای وابسته 
 رهیاب ناسا
 هواپیمای الکتریکی

منابع

خودروهای عرضه شده در ۲۰۰۹ (میلادی)
علم در ۲۰۰۹ (میلادی)
علم در ۲۰۱۳ (میلادی)
کالیفرنیا در ۲۰۱۳ (میلادی)
معرفی‌شده‌های ۲۰۰۹ (میلادی)
نیروی خورشیدی در سوئیس
ویکی‌سازی رباتیک
هواپیماهای ملخ‌پیشین چهارموتوره
هواگردهای ساخت سوئیس
هواگردهای آزمایشی اهل سوئیس
هواگردهای برقی
هواگردهای چهارموتوره

**Full target**

تأمین سرمایه 
برتراند پیکارد پروژه سولار ایمپالس را در نوامبر ۲۰۰۳ پس از انجام یک بررسی امکان‌پذیری با همکاری مؤسسه پلی تکنیک فدرال لوزان (دانشگاه EPFL) شروع کرد. بنیان‌گذار همکار، آندره بورشبرگ، به عنوان یک مهندس مکانیک کار مدیریت ساخت هواپیماها و آماده‌سازی مأموریت‌های پروازی را انجام داد. در سال ۲۰۰۹ آن‌ها یک تیم ۵۰ نفره از مهندسین و متخصصین فن از

**Published audit reason (not independent evidence)**

The model correctly identified the missing text required to fill the gap. It followed the instruction to provide only the text (though it provided a bit of context leading up to the gap, it accurately completed the span as requested by the task type). The Persian language is natural and matches the source text perfectly.


### Case 14 / span-filling / ریتا مارلی

ID: `ab11bcecb3e4d1629a0232d1eeaa6972a1526f91d109c66f1e30841d7634c2ff`

Record SHA256: `d173933b382f859fd1a5bf76ffe86270c00e23c80ce83810f607d485158086d7`

Source: `20231101.fa/train-00002-of-00004.parquet`, row 203549, article 5081033.

Assessment: **source_language_concern_native_confirmation_needed** (medium). Exact 82-character missing span. The target's در سطح بالایی خیابان Beachwood (roughly at an upper level of Beachwood Street) reads like a literal/malformed location translation; neighboring parentage text در لروی اندرسون و سینتیا is also awkward. These are inherited wording concerns, not confidently verified biographical falsehoods. The gap also cuts inside the quoted book title. Request native review before asserting a categorical language failure.

**Full learner input**

(فارسی) جای <GAP> را پر کن؛ فقط متن حذف‌شده را بنویس.

آلفاریتا کنستانتیا ریتا مارلی، (به انگلیسی: Alpharita Constantia Rita Marley) متولد (۲۵ ژوئیه ۱۹۴۶)، خواننده جامائیایی کوبایی، همسر سابق باب مارلی فقید خواننده برجسته جامایکا است.

زندگی شخصی 
ریتا در سانتیاگو دو کوبا، در لروی اندرسون و سینتیا "بداً جارات متولد شد. او <GAP> زن، نه فریاد: زندگی من با باب مارلی " توضیح می‌دهد که چگونه توسط عمه خود در جاده گرینویچ پارک بزرگ شد تا اینکه با همسرش باب مارلی آشنا شد.

ریتا شش فرزند دارد که سه تن از آنها فرزندان مشترک با باب مارلی هستند. باب دو فرزند دیگر ریتا را به عنوان فرزند خود پذیرفت و نام خانوادگی مارلی دارند.

کتاب‌ها 
_ ریتا مارلی، هتی جونز

_ نه زن، نه فریاد: زندگی من با باب مارلی

افراد زنده
اهالی سانتیاگو د کوبا
باب مارلی
خوانندگان رگی اهل جامائیکا
خوانندگان زن اهل جامائیکا
زادگان ۱۹۴۶ (میلادی)
موسیقی‌دانان اهل کینگستون، جامائیکا
موسیقی‌دانان رگی اهل جامائیکا

**Full target**

در سطح بالایی خیابان Beachwood واقع در کینگستون، جامائیکا بزرگ شد. او در کتاب " نه

**Published audit reason (not independent evidence)**

The model correctly identified and filled the gap with the exact text from the reference, following the instruction to provide only the missing text. The Persian language usage is natural and accurate.


### Case 15 / span-filling / پایان (رمان)

ID: `fffb7990f821df7eb607e89480eeb3babfa3ec1e785c38442a288647141f7a29`

Record SHA256: `d0342cb433f1bf212c1032672b235e00dd8f39220d674223324798a2fcb00fd8`

Source: `20231101.fa/train-00000-of-00004.parquet`, row 26880, article 179191.

Assessment: **valid_narrative_cloze_with_source_noise** (medium). Exact 189-character span reconnects Friday's reaction, leading the children to the island, and the Ishmael clause whose continuation is visible. A semantically plausible narrative cloze, though plot/name-specific wording is not uniquely derivable. Surrounding source has obvious typos/run-on punctuation, including بچه‌ها ا قایق and یه دستور. Do not confuse that source noise with newly invented repair text or a target-boundary bug.

**Full learner input**

(فارسی) جای <GAP> را پر کن؛ فقط متن حذف‌شده را بنویس.

پایان  نام آخرین کتاب از مجموعه ماجراهای بچه‌های بدشانس است. این کتاب توسط دنیل هندلر با نام مستعار لمونی اسنیکت نوشته شده و برت هلکوئیست آن را تصویرگری کرده‌است.

نسخه انگلیسی 
منتشر شده در ۱۳ اکتبر ۲۰۰۶ در آمریکا و در ۳۲۴ صفحه

داستان 
ویولت-کلاوس و سانی بودلر به همراه کنت الاف از هتل دینومان آتش گرفته با قایق کارملیتا اسپاتس در اقیانوس پیش می‌روند. بعد از مدتی سرگردانی در اقیانوس طوفانی شدید درمی‌گیرد و کنت الاف به بیرون از قایق افتاده می‌شود. سپس طوفان آنها را به یک تپهٔ دریایی می‌رساند. بچه‌ها ا قایق پیاده می‌شوند و کنت الاف را در گوشه ای می‌بینند. در همین حال دختری کوچک از دور می‌آید که جمعه نام دارد و در همان موقع کنت الاف به هوش می‌آید. جمعه قدرنشناسی کنت الاف را <GAP> خاک‌های رس فرورفته است) رو به رو می‌شوند که همه مجبورند از دستورها او اطاعت کنند. همچنین بچه‌ها متوجه می‌شوند که همهٔ اهالی آن جزیره لباس‌های سفید می‌پوشند و همهٔ آنها آب نارگیل مرموزی را می‌نوشند و غذای آنها هم همیشه یکنواخت است. آنها می‌فهمند که هر سال یکبار مد اقیانوس قسمت پایینی جزیره را در خود فرو می‌برد و اهالی به قسمت بالایی جزیره می‌روند. آن روز روز انتخاب نام دارد و اهالی جزیره می‌توانند با بلمی که در طول سال ساخته می‌شود به شهر برگردند-که به‌طور عجیبی هیچ‌کدام از اهالی تا به حال از جزیره نرفته‌است.
در قسمت بالایی جزیره مکانی به نام باغ گیاه‌شناسی وجود دارد که وسایل بلااستفاده -تقریباً همهی چیزهایی که بر اثر طوفان به جزیره آورده می‌شود یه دستور ایشماییل به آنجا برده می‌شود. همچنین در آنجا درخت سیبی تلخ وجود دارد.
در این داستان بودلرها به راز بزرگ ایشماییل پی می‌برند/رازی شگفت‌انگیز دربارهٔ والدین خود می‌فهمند/کنت الاف می‌میرد/بچه‌ها با کیت اسنیکت رو به رو می‌شوند و از راز درخت سیب تلخ آگاه می‌شوند

نسخه فارسی 
جلد پایانی این کتاب با نام پایان ترجمه و توسط انتشارات ماهی منتشر شده‌است.

منابع

رمان‌های ۲۰۰۶ (میلادی)
رمان‌های آمریکایی ۲۰۰۶ (میلادی)
رمان‌های دنباله
رمان‌های کودکان آمریکایی
رمان‌های مورد اقتباس در مجموعه‌های تلویزیونی
کتاب‌های کودکانه ۲۰۰۶ (میلادی)
کتاب‌های هارپرکالینز
کشتی‌شکسته‌ها در ادبیات داستانی
ماجراهای بچه‌های بدشانس

**Full target**

می‌بیند به همین دلیل او را در آنجا رها می‌کند و بچه‌ها را به سوی جزیرهٔ بی‌نام و نشان خودش راهنمایی می‌کند.
بودلرها در آن جزیره با تصمیم گیرندهٔ آنجا که ایشماییل نام دارد (و همیشه پاهایش در

**Published audit reason (not independent evidence)**

The assistant correctly identified and filled the gap in the Persian text, maintaining the exact wording and flow of the original reference. The transition between the filled text and the subsequent sentence is seamless.

