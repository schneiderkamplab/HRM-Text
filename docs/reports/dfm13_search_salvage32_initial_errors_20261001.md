# Search Salvage: First Seven Outcomes

CPU inspection while PID 3008803 continues unchanged. Root:
`data/dfm13/search-salvage32-20261001`. Seven terminal: four automated
keeps, three citation-validation errors. All three have saved candidates and
completed raw reviews. None is a provider failure or transport timeout.

| Task prefix | Failure | Evidence and safe disposition |
| --- | --- | --- |
| `99fe14a8` | HTML links unsupported | Answer contains Markdown citations to observed URLs plus table `<br>` formatting, not an HTML hyperlink. Formatting-only recovery can replace `<br>` with a space in a new candidate, retaining the original. Do not relax HTML hyperlink validation globally. Semantic claims about gaming/updates still need independent assessment. |
| `0cfb74ac` | Unobserved hyperlink | Generated citation omits `www.` from an actually observed Liverpool article URL; path matches exactly. A case-specific new candidate may restore the exact observed URL. Do not establish a global www/non-www equivalence rule or infer redirects. The cached article's historical applicability still requires checking. |
| `31dbdb34` | No supporting-page citation | Actual answer has no URL. This is not punctuation parsing. It adds proposed coding exercises and timing rules without differentiating sourced principles from illustrative suggestions. Do not cosmetically append a source and call it verified. Defer or independently scope a source-grounded correction; the single generation attempt has been used. |

The raw reviewer emitted no confirmed errors for each, but that does not override
traceability checks or certify semantic support. Any deterministic formatting
recovery must preserve original artifacts, bind old/new candidate hashes,
revalidate rendering/citations, and remain held pending substantive review.
No paid calls, new inference, active module edits, or server changes were made
for this diagnosis. Remaining salvage jobs continue sequentially at one request.
