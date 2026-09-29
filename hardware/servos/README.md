# Servo reference: Kitronik 25105 / FS90MG-CL

The head and both arms use Kitronik Clippable Servo 25105, identified by Kitronik
as the Feetech FS90MG-CL. Each axis uses the supplied round disk horn and its
matching center screw. Follow the [build guide](https://demartinistudios.github.io/blooglyblob/)
for drilling, fastening and fitting the horns.

## Manufacturer references

- [Product page](https://kitronik.co.uk/products/25105-clippable-servo)
- [Technical drawing](https://resources.kitronik.co.uk/pdf/25105-kitronik-clippable-servo-technical-drawing.pdf): case, mounting ears, output and mounting-hole dimensions.
- [FS90MG-CL datasheet](https://resources.kitronik.co.uk/pdf/25105-kitronik-clippable-servo-fs90mg-datasheet.pdf): 21T spline and nominal 180° travel over 500–2500 µs.

Use the product-specific documents when selecting a replacement. Generic FS90MG
listings describe different analog/digital variants, spline counts and envelopes;
the name alone does not establish compatibility. The supplied horn center screw
is a separate interface from the M2 servo mounting screws.

## Nominal case dimensions

These dimensions are taken from the Kitronik drawing and used by the CAD
reference. They do not include print clearance or establish physical fit.

| Dimension | mm |
| --- | --- |
| Main body length × width | 22.5 × 12.1 |
| Main rectangular case height envelope | 22.4 |
| Height excluding spline / including spline | 26.7 / 30.7 |
| Mounting-ear overall span | 32.3 |
| Ear underside / top from case bottom | 15.7 / 18.2 |
| Mounting-hole spacing / diameter | 27.7 / 2.2 |
| Output axis to nearer mounting hole | 8.7 |
| Spline envelope diameter | 4.86 |

The CAD reference simplifies the molded case and output cap. Axis-to-case-end
placement uses symmetry inferred from the drawing.

## Measured disk horn

The [reference photographs](../reference-photos/README.md) show the supplied kit
and both disk faces. The following are measurements of the reference horn, not
manufacturer tolerances or measurements inferred from photograph scale.

| Feature | Diameter | Axial thickness / protrusion |
| --- | --- | --- |
| Flat disk plate | 23.55 mm | 1.61 mm |
| Servo-facing raised center | 6.75 mm outside | 2.17 mm above the plate face, derived as 3.78 − 1.61 |
| Outer raised center | 5.44 mm outside | 0.87 mm above the plate face, derived as 4.65 − 3.78 |
| Plate plus servo-facing raised center | — | 3.78 mm |
| Overall, including both raised centers | — | 4.65 mm |

The measured installed height is 3.33 mm from the uppermost flat plastic
output-cap face to the disk's broad underside, or 4.94 mm to its upper flat face.
The selected opposite mounting holes are approximately 18 mm apart and originally
about 1.1 mm in diameter; the guide specifies drilling that pair to 2.2 mm with
the horn removed. Other pairs are about 16 and 20 mm apart, so the holes do not
form a uniform four-hole pattern. Use the guide's current fastener allocations.

The horn envelope omits the spline socket, center bore and mounting holes.
The 6.75 mm measurement is the outside of the raised center, not the socket
diameter. Do not infer spline engagement or installed height from that envelope.
Keep access to the supplied center screw; the printed adapter fastens to the horn
rather than replacing its spline.

## Fitting and operating positions

The application uses a fixed **1000–2000 µs window at 50 Hz**. The fitting command
`make pi-servo-fit` holds the left arm at 2000 µs, right arm at 1000 µs and head at
1500 µs before the guide's horn installation steps. See
[servo setup and maintenance](../../docs/software/maintenance.md) and the
[servo fitting contract](../../docs/software/validation.md#servo-fitting-contract).

The datasheet gives no case-referenced angular zero or marked-tooth datum.
Horn indexing establishes the attached part's orientation. Nominal datasheet
travel does not establish loaded clearance, cable freedom or usable travel in the
assembled robot; physical qualification remains separate from the reference data.
