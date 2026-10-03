# UCloud training credit

`UCloud-logo.svg` is the original logo supplied by the user on 2026-09-22.
`../assets/ucloud.png` is its 1200-pixel-wide transparent raster export for Flutter.
The welcome screen places it beside the DFM logo, wrapping below on narrow
screens, with the exact caption **Trained on SDU UCloud**.

The SVG contains live text using IBM Plex Sans. Rendering used the regular font
from [IBM Plex revision 763c36ef](https://github.com/IBM/plex/blob/763c36ef9117782905ae010056dfbe8fd2653a25/packages/plex-sans/fonts/complete/ttf/IBMPlexSans-Regular.ttf)
and `rsvg-convert`. With that font available to Fontconfig, regenerate from the
repository root:

```sh
rsvg-convert --width 1200 --output native/app/assets/ucloud.png native/app/branding/UCloud-logo.svg
```

Check `fc-match 'IBM Plex Sans'` before rendering to avoid font substitution.
The app bundles only the PNG, requiring no fonts, SVG runtime dependency or
network access. The original SVG remains tracked as the branding source.
