# Release descriptions

Every published release must have a self-contained description. This requirement
applies to all future patch, minor and major versions, including 0.1.3+, 0.2.x
and later. Users must not need to read earlier releases to install the app or
use any feature shipped in their version. A changelog alone is insufficient.

Maintain the exact published description in `native/app/releases/VERSION.md`.
Use [TEMPLATE.md](TEMPLATE.md) as the coverage checklist and consult the previous
complete description for wording; verify every retained claim against the new
release's source and artifacts. Do not copy newer features into historical notes,
preserve obsolete restrictions after they are lifted, or imply that a roadmap
feature has shipped. When a capability is unavailable on a platform, state that.

Before publishing:

1. Document downloads/install/upgrade steps, platform/backend/signing limits,
   model delivery/selection and networking consent, chat/context/compaction,
   desktop API setup/examples/limits, headless commands, feedback/privacy,
   version-specific changes, provenance, validation and checksums.
2. Check UI labels, commands, defaults, paths and supported API fields against
   that release's source. Identify exact bundled weights and actual test limits.
3. Publish from the versioned Markdown file; read GitHub's body back and verify it
   matches. For a notes-only edit, verify assets, checksums, tag target and release
   visibility remain unchanged. Keep the newest supported version marked latest.

```sh
gh release edit dfm-mimir-vVERSION --notes-file native/app/releases/VERSION.md
```

Documentation updates do not require rebuilding packages or moving tags. This
policy does not pre-authorize or create future releases; apply it when preparing
each requested release.

## Versioned descriptions

- [0.1.1](0.1.1.md)
- [0.1.2](0.1.2.md)
- [0.1.3](0.1.3.md)
- [0.1.4](0.1.4.md)
