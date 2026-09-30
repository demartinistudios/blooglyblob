# Build guide authoring

Start with the [hardware workflow](../README.md). There is one authored guide,
`src/`, versioned in ordinary Git. `dist/` is ignored build output. The guide
consumes selected CAD, print, assembly and reference inputs when built; the CAD
registry and delivery do not pin guide content. Public assembly instructions
belong in the guide; contributor workflow and readiness evidence belong here or
in the [current review summary](REVIEW.md). Detailed working notes stay private.

## Build and preview

Use Python 3.12 or 3.13 from the repository root:

```sh
make hardware-check
make guide-build
python3 -m http.server 8769 --bind 127.0.0.1 --directory hardware/build-guide/dist
```

Keep the preview at [http://127.0.0.1:8769](http://127.0.0.1:8769) so browser
progress remains available. Preview builds can be useful while publication is
blocked; a successful build is not publication approval. A validated build replaces
the preview; an interrupted swap retains an ignored `.guide-previous/` backup
that the next build restores before checking inputs.

The builder copies authored content and derives data/downloads from their own
homes, without retaining source copies in the guide:

- Required and optional STLs selected by the part catalog (excluding retired
  exports), and the exact editable projects selected by the print manifest,
  their object-settings CSV and project thumbnails. ZIP timestamps are fixed for
  reproducible packages. Plate thumbnails show layouts, not sliced toolpaths.
- Assembly power/signal tables and the selected print quantities and estimates.
- External component-document links selected by the
  [reference catalog](../references/community-20260925/catalog.json). Publisher
  PDFs are not stored in Git or bundled with the guide. Keep optional research
  downloads in ignored `hardware/.work/`; builds never fetch or require them.

The `print-plates` step is the single printing page. `#printing` links redirect there,
including links that locate a particular part’s plate. Plate layouts, individual
STL links and settings expand within that step using the main content of
`src/repeat-build.html`, bundled at build time. Edit that one authored source;
the standalone URL remains available for bookmarks and non-JavaScript readers.

It checks package metadata and local references. Keep `src/` limited to authored
pages, text, data, diagrams, templates and pictures; do not add alternate guide
versions, CAD/project copies or copied datasheets.

## Review an input or guide change

Follow the [instruction design guidance](INSTRUCTION-DESIGN.md) for action
illustrations, concise copy, page layout and visual review.

Use `python3 hardware/tools/cad/impact.py PART_ID` to start an impact review, then
cover changed process, hardware, electrical and software dependencies too.
Unknown relationships require review. In the ignored local work record, name each
affected surface and record whether it changed, was reused with unchanged
relevant dependencies, or was reviewed:

- Steps and service/repeat-build instructions, and step IDs and their links.
- Part/supply/plate cards, fastener allocations, quantities, estimates and downloads.
- Models, diagrams, assembly views, custom/stand views, templates and hardware keys.
- Wiring/reference pages, component specifications and software commands.

Prefer bench preparation before installation: solder, insulate, label and check
loose components or harnesses before fastening them to printed parts. Where
length depends on the assembly, test-route and mark first, then return to the
bench for hot work. Finish soldered harnesses before plugging them into mounted
boards; keep final routing, restraint and connector seating in the installation
step. Review access before closing covers or fitting parts that obstruct tools.

Check the assembly meaning visually: mating surfaces, clearances, access and
fastener engagement need review even when a generator succeeds.

Use [review-status.json](review-status.json) as a manual release checklist and
[REVIEW.md](REVIEW.md) for concise public evidence and limitations.
After changing the guide or its inputs, mark affected sections pending. Before
publication, inspect those sections against the intended release revision and
record `reviewed_revision`, reviewer and evidence. The checker validates the
checklist entries; it does not infer freshness or perform the human review.
There is no automatic fingerprint or repository-wide dependency graph.

`consistency.py check` checks quantities, references and documented commands.
Pending manual review permits local previews. `consistency.py check --publication`
also requires the release checklist; it does not establish physical fit.

## Optional authoring tools

Ordinary checking/building uses committed authored assets. These generators need
additional local tools only when changing those assets; review generated diffs:

- `hardware/tools/guide/render_models.py` renders CAD views and front-fastening
  sections. Install NumPy, Pillow, Numba and trimesh, and supply a licensed local
  TrueType font. Render for review with
  `python3 hardware/tools/guide/render_models.py --output hardware/.work/guide/UNIQUE-RUN --font /path/to/font.ttf`.
  The output directory must be new; add `--write` only to adopt reviewed images
  into `src/`. Source identity and scene/dimension review gates must pass for the
  selected CAD revision; do not bypass them to force new pictures.
- `hardware/tools/guide/render_hand_arm_actions.py --output NEW_DIR --font FONT`
  renders magnet, horn, strap and saddle installation close-ups from the same checked
  CAD source. It checks the receiving features before drawing nominal magnets and
  drilled horns, and records source hashes and dimensions. Inspect scratch images
  before using `--write`. Broad model rendering also applies these action views
  whenever their public paths are selected, so it cannot restore empty-seat views.
- `hardware/tools/guide/diagrams.py` writes schematic SVGs into `src/assets/`.
- `hardware/tools/guide/master_wiring.py --out PATH.svg` draws the complete wiring
  reference. Review its terminal assignments against `hardware/assembly/electrical.json`
  and the lighting steps before adopting `src/assets/circuits/master-wiring.svg`.
  Each component appears once; draw continuous wires between registered terminals.
- `hardware/tools/guide/cartoons.py` draws purchased-part, consumable, fastener
  and tool illustrations. Use `--out DIR` for review and naming IDs for a subset.
  Use product drawings/photos as references, consistent projection and scale,
  and do not store product photos in the repository.
- `hardware/tools/guide/make_downloads.py` generates film, foam and screw-key
  PDF templates. It requires `rsvg-convert`.

## Browser verification and progress

Install Node.js 22 or newer, then the pinned browser-test dependencies:

```sh
make guide-setup
make guide-browser
```

On Linux, use `make guide-setup GUIDE_SYSTEM_DEPS=1` when Chromium system
packages also need installing. Setup is separate from offline checks.

`make guide-browser` builds the guide and starts its own temporary loopback server; an
existing preview is not required or interrupted. Set `BGB_CHROME` to use a local
Chrome executable instead of the downloaded Chromium. Reports go to a new
ignored `hardware/.work/guide/browser-*/` directory.

The check uses an isolated context, visits desktop/mobile routes, checks local
links/images and checks that saved progress is read without migration. Inspect its report and screenshots
for assembly meaning as well as layout. It does not change your browser data.

Progress is saved in the reader's browser under `blooglyblob-guide`. Step IDs are
descriptive slugs such as `board-cover-nuts`, and displayed numbers follow build
order. There is no migration layer: when a step is renamed, split or removed,
saved ticks for its old ID stay stored but no longer count, because progress
counts only current build steps. Update every `{step:…}` reference, `#step-…`
link and part `steps` list when a step ID changes.

## Publication readiness

Website checks and build-kit qualification are separate. Before an authorized
website deployment, run `python3 scripts/check_pages.py` and `make guide-browser`.
These require current-input integrity, a successful build and browser checks;
pending qualification reviews remain visible in the job summary.

Before claiming a qualified build kit, run
`python3 hardware/tools/validation/check.py --publication` and complete the
manual release checklist and affected visual/assembly review against the same
inputs. See [REVIEW.md](REVIEW.md) and the
[release checklist](../../docs/release/checklist.md) for current limitations and
qualification scope. Passing software checks does not establish physical fit.

Documented commands are checked during ordinary builds too. `make pi-servo-fit`
and startup share the fixed fit/rest positions; movement remains within
1000–2000 µs at 50 Hz. See [software validation](../../docs/software/validation.md).
Do not invoke hardware merely to check that a command exists.

Deployment uses [the Pages workflow](../../.github/workflows/guide-pages.yml),
with repository Settings → Pages → Source set to "GitHub Actions". Contributor
checks do not themselves authorize deployment. Keep preview, deployment and
physical qualification distinct when reporting completion.
