# Release descriptions

Each release description must stand alone: do not require users to read earlier
releases to learn how to install or use the shipped features. Keep installation,
platform/backend limits, model selection and networking consent, context controls,
desktop API setup and limitations, headless commands, feedback/privacy, provenance,
validation and checksums alongside the version-specific changes.

- [0.1.2](0.1.2.md)

Publish a description with `gh release edit dfm-mimir-vVERSION --notes-file
native/app/releases/VERSION.md`, then read the release back and verify that its
body matches. Documentation updates do not require rebuilding packages or moving
tags. Check command examples and UI labels against that release's source.
