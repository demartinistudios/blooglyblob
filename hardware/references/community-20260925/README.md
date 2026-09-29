# Component reference catalog — 2026-09-25

[Catalog](catalog.json) maps E01–E25, F1/F2, R1/R2, C02/C03/C04 and C08 to publisher product pages, pinouts, drawings and datasheets. Documents are external links. `download_url`, when present, selects the document endpoint for the guide; otherwise it uses `official_url`. Publisher PDFs are not version controlled or bundled. Optional research downloads belong in ignored `hardware/.work/` and are never required by a build.

The catalog is a reference supplement. It does not approve substitutions, qualify physical fit, change electrical limits or advance CAD/delivery acceptance.

## Coverage and limits

- Manufacturer-hosted PDFs cover the Kitronik servo, Adafruit eye boards and Pixel Shifter, Panasonic capacitor, Raspberry Pi board, SanDisk card, MEAN WELL supply and cord catalog, Adafruit power-donor cable, YAGEO resistors and Zotefoams LD45. The two Kitronik links identify the manufacturer PDFs inspected on 2026-09-17.
- The Eaton S505H PDF is Eaton Technical Data 4406, effective June 2023, manufacturer-authored and hosted by LCSC. It includes the 1 A and 3.15 A selections. The catalog selects the verified distributor-hosted PDF because Eaton’s download endpoint is unreliable.
- The WAGO connector PDF is manufacturer-authored and hosted by NetXL; the catalog also links directly to WAGO's exact product page. This supplier mirror is explicitly identified.
- Exact product pages provide references for the Adafruit connector cables, mouth stick, speaker pair, button and quick-connect leads, plus Waveshare USB TO AUDIO and its supplied extension. The button has a publisher raster drawing link; it is not mislabeled as a PDF. The servo horn and center screw lack a separate manufacturer dimensional specification.
- Switchcraft 721AU and K&J D31 have verified official PDF links. Family documents are labeled and must be read for the specified variant.
- **E05 is Adafruit6026.** The exact product and manufacturer drawing establish the100-pixel,100mm-pitch strand. Adafruit family guides describe copper-marked positive conductors and factory lead colors. Lot variation remains possible; confirm identification and test input direction before cutting. Connector sex is not direction.
- **E24 and E25 are generic specifications without selected SKUs.** E25 requires four equal-height adhesive feet fitting the Ø14mm post faces. There is no defensible exact-model datasheet to attach.
- **C08 is a candidate, not a verified installed purchase.** K&J D31 matches the stated size. Retention and adhesive compatibility remain to be tested.
- **C02/C03/C04:** the user's selected [Coscom LD45 listing](https://coscomcosplaysupplies.com/products/plastazote-ld45) explicitly offers white 4 mm sheets. Its default selector is 2 mm, so purchasers must select 4 mm. The [Zotefoams LD45 sheet](https://www.zotefoams.com/wp-content/uploads/2025/03/PIS-A013-Plastazote-LD45.pdf) is Product Information Sheet A013, Issue 1 Revision 1, June 2026. It gives typical material properties, not guaranteed optical transmission. The superseded December 2017 URL returned 404; the current URL was obtained from Zotefoams' product information index.

## Verification and updates

The owner selected external links on 2026-09-26. The [link verification record](link-verification.json) covers all catalog URLs and the three generic servo datasheets. Direct PDF retrieval checks the PDF signature rather than treating an HTML error page as a document. Browser retrieval verified Panasonic and product pages that blocked or timed out under command-line access. These are dated availability observations; external sites can change.

Edit `catalog.json` as the authority, then update the guide's reference presentation and page. Preserve part identity, exact-model/family limitations and publisher or supplier-host attribution. Verify replacement links against the intended document before changing them. Do not recreate download-and-copy generators or add manufacturer PDFs to the source tree.

`make hardware-check` checks external URL shape, catalog/guide agreement, rendered-page links and the absence of publisher PDFs in the reference/servo directories. `make guide-browser` verifies the built guide. These contributor checks remain offline; deliberate live link verification is separate.

`tool-product-identity.json` records the separate tool check: Adafruit 136 is Ladyada’s Electronics Toolkit, whose contents link to Adafruit 2034, Digital Multimeter Model 9205B+. The current guide T03 photo uses 2034 but its purchase link pointed to 136 when checked; the guide owner was notified.
