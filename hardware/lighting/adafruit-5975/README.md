# Selected eye board: Adafruit 5975

User-approved 2026-09-17 after viewing the product photo. Quantity: **two**, one per eye. Use behind removable Plastazote eye diffusers; mounting should permit replacement without glue.

- [Product and published envelope](https://www.adafruit.com/product/5975): 12.3 × 11.3 × 6.2 mm, M2 mounting, 3-pin JST-SH input/output.
- [Adafruit PCB source](https://github.com/adafruit/Adafruit-NeoPixel-Breakout-PCB), linked by the [manufacturer downloads page](https://learn.adafruit.com/adafruit-neopixel-breakout/downloads).
- Local unmodified source: [Eagle board](Adafruit-NeoPixel-JST-SH-Breakout.brd), [upstream README](upstream-README.md), [upstream license](upstream-license.txt). Designed by Limor Fried/Ladyada for Adafruit Industries; upstream identifies Creative Commons Attribution/Share-Alike. Preserve the supplied attribution and license with redistribution of these reference files.
- [Extracted mechanical interface](mechanical-interface.json), including source SHA-256, exact hole coordinates, outline dimensions and limits of the extraction.

The Eagle file uses millimeters. Two plain holes have diameter 2 mm and centers (0, +4.318) and (0, −4.318): **8.636 mm apart**. The LED is centered at (0, 0). Layer 20 outlines a 12.192 × 11.43 mm rounded board, with 2.54 mm corner radii. These are CAD nominal dimensions, not physical measurements or print clearances. The small difference from the product listing is retained explicitly rather than rounding the mounting pattern.

Do not infer the full front/back component stack from the overall 6.2 mm envelope. Leave access for both connector plugs and wiring bends, and inspect the manufacturer 3D model or an actual board before finalizing the holder. Holders will use clearance fasteners and nuts; screw lengths and support pad geometry follow that inspection.

## Assembly use

Current CAD includes removable P06 holders and P07 bezels, with P08 feed-through
and strain relief. The selected [current design](../../cad/CURRENT-DESIGN.md),
[assembly allocations](../../assembly/hardware.json) and
[electrical tables](../../assembly/electrical.json) define the maintained build.
This reference does not replace those quantities, fastening choices or wiring.

Flexible wiring, physical plug access, diffuser fit and optical performance still
need physical review. The nominal foam thickness is 4 mm; it is not a measured
fit or guaranteed optical specification. Preserve access for both plugs and
avoid deriving the full component stack from the product envelope alone.
