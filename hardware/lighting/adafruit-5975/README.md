# Selected eye board: Adafruit 5975

The build uses **two** Adafruit 5975 boards, one per eye, behind removable
Plastazote diffusers. The boards fasten to printed holders so they can be replaced
without glue.

- [Product and published envelope](https://www.adafruit.com/product/5975): 12.3 × 11.3 × 6.2 mm, M2 mounting, 3-pin JST-SH input/output.
- [Adafruit PCB source](https://github.com/adafruit/Adafruit-NeoPixel-Breakout-PCB), linked by the [manufacturer downloads page](https://learn.adafruit.com/adafruit-neopixel-breakout/downloads).
- Local unmodified source: [Eagle board](Adafruit-NeoPixel-JST-SH-Breakout.brd), [upstream README](upstream-README.md), [upstream license](upstream-license.txt). Designed by Limor Fried/Ladyada for Adafruit Industries; upstream identifies Creative Commons Attribution/Share-Alike. Preserve the supplied attribution and license with redistribution of these reference files.
- Local unmodified 3D model: [5975-NeoPixel-Breakout.step](5975-NeoPixel-Breakout.step), byte-identical to `5975 NeoPixel Breakout.step` in [Adafruit CAD Parts](https://github.com/adafruit/Adafruit_CAD_Parts). Copyright (c) 2016 Adafruit Industries, [MIT license](../../../LICENSES/Adafruit-CAD-Parts-MIT.txt).
- [Extracted mechanical interface](mechanical-interface.json), including source SHA-256, exact hole coordinates, outline dimensions and limits of the extraction.

The Eagle file uses millimeters. Two plain holes have diameter 2 mm and centers (0, +4.318) and (0, −4.318): **8.636 mm apart**. The LED is centered at (0, 0). Layer 20 outlines a 12.192 × 11.43 mm rounded board, with 2.54 mm corner radii. These are CAD nominal dimensions, not physical measurements or print clearances. The small difference from the product listing is retained explicitly rather than rounding the mounting pattern.

The overall 6.2 mm product envelope does not define the full front/back component
stack. Keep both connector plugs and wiring bends accessible; use the maintained
assembly instructions for screws, nuts and washers.

## Assembly use

The eye boards mount in P06 holders. Follow the
[build guide](https://demartinistudios.github.io/blooglyblob/) for diffuser placement,
fastening and wire routing. The selected [current design](../../cad/CURRENT-DESIGN.md),
[assembly allocations](../../assembly/hardware.json) and
[electrical tables](../../assembly/electrical.json) define the maintained build.
This reference does not replace those quantities, fastening choices or wiring.

Flexible wiring, physical plug access, diffuser fit and optical performance still
need physical review. The nominal foam thickness is 4 mm; it is not a measured
fit or guaranteed optical specification. Preserve access for both plugs and
avoid deriving the full component stack from the product envelope alone.
