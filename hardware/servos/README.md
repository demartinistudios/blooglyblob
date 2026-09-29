# Servo references — Kitronik 25105 / FS90MG-CL

## Identified hardware — 2026-09-17

The user's [kit photograph](../reference-photos/kitronik-25105-servo-and-horns.jpg) clearly shows **Kitronik Clippable Servo 25105**. Kitronik identifies this product as **Feetech FS90MG-CL**, a digital position servo supplied with four plastic horns. This resolves the model-family uncertainty for the photographed unit. The user subsequently confirmed the same servo model and horn kits are used for all three axes.

Use these product-specific sources ahead of the generic FS90MG documents below:

| Document | Source | Evidence |
| --- | --- | --- |
| Kitronik 25105 technical drawing | [Kitronik drawing](https://resources.kitronik.co.uk/pdf/25105-kitronik-clippable-servo-technical-drawing.pdf) | Servo case, mounting ears, output and mounting-hole dimensions; visually inspected in full. |
| Kitronik FS90MG-CL datasheet | [Kitronik datasheet](https://resources.kitronik.co.uk/pdf/25105-kitronik-clippable-servo-fs90mg-datasheet.pdf) | Explicit FS90MG-CL identification, 21T spline, 180-degree operating travel at 500–2500 microseconds. |

Reviewed without modification on 2026-09-17 through links on the [manufacturer product page](https://kitronik.co.uk/products/25105-clippable-servo). The drawing has one page; the datasheet has two.

### CAD cross-check

All twelve nominal dimension parameters below match the Kitronik drawing. No dimension change to the current mounts was required after identifying 25105. This confirms the reference specification, not the physical fit of a print.

| Dimension | Drawing / current CAD, mm |
| --- | --- |
| Main body length × width | 22.5 × 12.1 |
| Main rectangular case height envelope | 22.4 |
| Height excluding spline / including spline | 26.7 / 30.7 |
| Mounting-ear overall span | 32.3 |
| Ear underside / top from case bottom | 15.7 / 18.2 |
| Mounting-hole spacing / diameter | 27.7 / 2.2 |
| Output axis to nearer mounting hole | 8.7 |
| Spline envelope diameter | 4.86 |

The drawing specifies 21 teeth, consistent with the product-specific datasheet. Keep the supplied matching horn and center screw; do not substitute a horn based only on another FS90MG listing. The modeled rectangular case and cylindrical output cap remain conservative simplified envelopes, not a detailed reproduction of every molded feature. Axis-to-case-end placement uses the earlier symmetry inference from the drawing.

### Horns and measurements still needed

The user supplied [both disk faces](../reference-photos/README.md#disk-horn-both-faces--2026-09-17), then measured both raised centers. These dimensions describe axial thicknesses.

| Feature | Diameter | Axial thickness / protrusion |
| --- | --- | --- |
| Flat disk plate | 23.55 mm | 1.61 mm |
| Servo-facing raised center (splined side) | 6.75 mm outside | 2.17 mm above the adjacent plate face, derived as 3.78 − 1.61 |
| Outer raised center (opposite side) | 5.44 mm outside | 0.87 mm above the adjacent plate face, derived as 4.65 − 3.78 |
| Plate plus servo-facing raised center | — | 3.78 mm, measured |
| Overall, including both raised centers | — | 4.65 mm, measured |

These are measured inputs and derived dimensions, with no added print clearance. The hidden, unplaced Fusion reference now models the external envelope with both raised centers. It omits the spline socket, screw bore and mounting holes. The 6.75 mm value is the **outside** of the hub, not the grooved socket diameter. Do not use this filled envelope to infer spline engagement or installed height.

The plate lies at local Z = 0…1.61 mm; the servo-facing hub extends to −2.17 mm and the outer hub to +2.48 mm. Both protrusions are expressions driven by the measured thicknesses. The component stays at the existing staging location, separate from the assembly.

Installed height is now measured: 3.33 mm from the uppermost flat plastic output-cap face to the broad flat disk underside, explicitly confirmed by the user. Adding the 1.61 mm plate gives 4.94 mm to its upper flat face. The selected opposite pair is approximately 18 mm with approximately 1.1 mm holes. The user also found other-axis pairs at approximately 16 and roughly 20 mm; these are not a uniform four-hole pattern. P14 r1 uses only the 18 mm pair, with user-approved enlargement to 2.2 mm and two new M2×6 screws/nuts. The original center screw remains unchanged. Preserve center-screw access and use positive screw attachment for torque transfer; a round rim pocket alone does not establish reliable torque transmission. Final clearance will be checked with a small print before committing the dome interface.

The kit photograph shows a disk, single-arm, double-arm and cross-shaped horn, plus loose screws. The ruler is useful for approximate scale, but perspective and differing part positions prevent precision measurement. The official documents inspected do not dimension the horns' outside profiles, hole patterns or thicknesses.

Current user-approved selection: the round disk horn for all three axes. This supersedes the initial double-arm-horn proposal. Retain access to the original center screw and attach the printed adapter to the supplied horn. No printed spline is planned. For layout, ruler measurements to about 0.5 mm are useful; for fixed hole locations, hub clearance and thickness, calipers to about 0.1–0.2 mm are preferable. These are measurement targets, not proven print tolerances. A small adapter fit test will establish the actual clearance.

Do not size horn screws from the nearby M2 servo-ear mounting standard. The supplied horn center screw is a separate interface. Kitronik's clippable leads also matter for service: the product page lists 250 mm leads and 34 mm crocodile clips. The photo does not show their ends, so the current build's connection arrangement and whether clips were replaced remain unconfirmed. Do not assume large clips can pass through the new cable openings.

## Earlier generic references

Reviewed 2026-09-16 for the Blooglyblob mechanical redesign. These Feetech documents are linked as background; the Kitronik-specific sources above now take precedence for the photographed servo.

| Document | Source | Useful pages |
| --- | --- | --- |
| FS90MG-digital-feetech.pdf | [Feetech](https://www.feetechrc.com/Data/feetechrc/upload/file/20200612/6372758119731571407558713.pdf) | Page 1: electrical/mechanical specs; page 2: control specs and dimensioned drawing |
| FS90MG-C001-2021-specification.pdf | [Feetech document hosted by Switch Science](https://pages.switch-science.com/comparison/files/feetech/micro-digital/FS90MG_datasheet.pdf) | Dated 2021-04-30; cover identifies FS90MG-C001. Page 4: mechanical/control specs; page 5: dimensioned drawing; page 7: interface |
| FS90MG-analog-legacy.pdf | [Feetech document hosted by Rhydolabz](https://www.rhydolabz.com/documents/24/FS90MG_specs.pdf) | Page 1: specs; page 2: control specs and dimensioned drawing |

## Differences among generic documents

- Digital documents specify 180 degrees of operating travel at 500-2500 microseconds, centered at 1500 microseconds. The legacy analog document specifies 110 degrees at 900-2100 microseconds; its mechanical limit is a separate specification.
- Digital drawings show a 22.5 mm body length, 12.1 mm width, 30.7 mm overall height including the output spline, 32.3 mm mounting-ear span, and 27.7 mm mounting-hole center spacing. The often-quoted 26.7 mm dimension excludes the spline. Confirm against the actual part before modeling fit.
- Digital spline specifications conflict: the Feetech-hosted document says 21T / diameter 4.86 mm, while the 2021 document says 20T / diameter 4.7 mm. Do not assume horn interchangeability.
- The legacy analog drawing has different dimensions (including 23.2 mm body length, 12.5 mm width, and 27 mm mounting-hole spacing). Its tabulated body height also differs from its drawing. Keep revisions separate.

## Runtime and mechanical limits

Use the current [servo setup and maintenance](../../docs/software/maintenance.md)
procedure and its fixed 1000–2000 µs operating window at 50 Hz. Datasheet travel does not establish safe
motion for an assembled mechanism. Installed units, clearance and operating
endpoints need checking before expanding travel; reference inspection does not
authorize PWM changes or physical servo commands.

## Endpoint orientation research, 2026-09-17

The user asked for source evidence on start/stop angles relative to the case. The exact 25105 datasheet and drawing give 1500 µs neutral, nominal 180° travel over 500–2500 µs, direction examples and a 21T spline, but no case-referenced angular zero or marked-tooth datum. Horn installation establishes the attached part’s orientation, with tooth indexing and per-unit calibration still to resolve. See [the research and design consequences](endpoint-orientation-research-2026-09-17.md). No servo commands or PWM changes were made.
