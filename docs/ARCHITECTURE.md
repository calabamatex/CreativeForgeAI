# Architecture

This document captures cross-cutting design decisions for the GenAI Creative
Automation Platform. It is the source of truth for *why* the pipeline behaves
the way it does, complementing the per-feature docs in this directory.

## Aspect-ratio generation strategy (P2-T2)

The platform produces campaign assets in four supported aspect ratios:
`1:1`, `9:16`, `16:9`, and `4:5` (see `src/models/enums.py::AspectRatio` and the
`aspect_ratios` validator in `src/models/campaign.py`).

There are two ways to produce those ratios. The choice is controlled by a single
opt-in flag on the campaign brief.

### Default: hero-plus-crop (one square hero, cropped locally)

**This is the default and unchanged behaviour.** For each product the pipeline:

1. Generates exactly **one** square "hero" image via a single image-generation
   API call (`CreativeAutomationPipeline._get_hero_image`). The square size is
   the backend's `DEFAULT_SQUARE_SIZE` (Firefly `2048x2048`; DALL-E and Gemini
   `1024x1024`).
2. For every locale × ratio, **center-crops** that hero to the target ratio
   locally via `ImageProcessor.resize_to_aspect_ratio`, then applies text/logo
   overlays and post-processing (`_generate_asset_for_ratio`). No additional
   image-generation API call is made per ratio.

This is cheap: one paid generation call per product, regardless of how many
ratios/locales are requested. The trade-off is that off-square ratios are crops
of a square composition rather than natively composed frames.

### Opt-in: native per-ratio generation

When `CampaignBrief.native_aspect_ratios` is `True`, the pipeline instead issues
**one image-generation API call per ratio** using that backend's native size for
the ratio (`_generate_native_for_ratio` → `service.ratio_to_size(ratio)`). Each
freshly generated image is still passed through `resize_to_aspect_ratio` to
enforce the exact frame (this covers documented nearest-ratio fallbacks, e.g.
DALL-E's `4:5`) and the same overlay/post-processing path.

In native mode the extra square hero call is skipped unless the product supplies
an existing hero asset (which is still loaded for reuse/reporting).

#### Cost guard — why this is opt-in

Native generation multiplies **paid** image-generation calls by the number of
ratios (and locales, for backends generating per locale). For a campaign with 4
ratios that is up to 4× the API spend versus the hero-plus-crop default. Because
this is a real cost amplifier, native generation is **opt-in only** and the
default is left untouched.

### Per-backend ratio → size maps

Each backend declares a `RATIO_SIZE_MAP` and inherits `ratio_to_size(ratio)` from
`ImageGenerationService` (`src/genai/base.py`). Unknown ratios fall back to the
backend's square size. The maps reflect each backend's *real* supported options:

| Ratio | DALL-E 3 (`openai_service.py`) | Gemini Imagen 4 (`gemini_service.py`) | Adobe Firefly (`firefly.py`) |
|-------|-------------------------------|----------------------------------------|------------------------------|
| `1:1`  | `1024x1024` | `1024x1024` (→ aspectRatio `1:1`)  | `2048x2048` |
| `9:16` | `1024x1792` | `1080x1920` (→ aspectRatio `9:16`) | `1152x2048` |
| `16:9` | `1792x1024` | `1920x1080` (→ aspectRatio `16:9`) | `2048x1152` |
| `4:5`  | `1024x1792` *(fallback)* | `1024x1280` (→ aspectRatio `3:4` *fallback*) | `1024x1280` |

**Documented fallbacks:**

- **DALL-E 3** supports only `1024x1024`, `1024x1792`, `1792x1024`. `4:5` has no
  exact size, so it maps to the nearest supported **portrait** (`1024x1792`); the
  pipeline then crops to the exact `4:5` frame.
- **Gemini Imagen 4** takes an `aspectRatio` string from the set
  `1:1, 3:4, 4:3, 9:16, 16:9`. `4:5` (0.8) is not native; the nearest portrait is
  `3:4` (0.75), so a `4:5` request resolves to aspectRatio `3:4`
  (`GeminiImageService._get_aspect_ratio`) and is cropped to exact `4:5`.
  `_get_aspect_ratio` was updated so it reflects the requested ratio rather than
  always returning `1:1`.
- **Adobe Firefly** accepts an explicit `{width, height}`, so `4:5` maps to an
  exact `1024x1280` frame (no crop fallback needed). Only Firefly's size map was
  added for this work — its **authentication (headers/tokens) is intentionally
  untouched** and is delivered separately in **P2-T1**.

### Status / what remains

Native per-ratio generation is **wired and unit-tested with mocked backends**
(no paid calls). It is still tagged *(in progress)* in the README because true
native output has not been verified against a live backend. That verification is
deferred until **P2-T1** (live Firefly auth) lands, after which the opt-in path
can be exercised end-to-end against real APIs and the docs promoted to "done".
