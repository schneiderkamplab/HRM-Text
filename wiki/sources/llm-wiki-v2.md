# Source Note: LLM Wiki v2 Gist

Last updated: 2026-05-20  
Confidence: medium  
Scope: External design inspiration for this repo wiki.

Source: https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2

## Takeaways Applied Here

- Keep a wiki rather than re-deriving project state each session.
- Use a schema document so agents know how to maintain the knowledge base.
- Separate session digests from stable semantic pages.
- Track confidence and supersession rather than treating all notes as permanent truth.
- Keep `AGENTS.md` as the entry point for future agents.

## Deferred Ideas

- hybrid search
- vector index
- entity graph
- automatic contradiction checks
- retention decay
- automatic session crystallization

This repo currently implements the minimal viable version: Markdown wiki, index, schema, and update rule.

