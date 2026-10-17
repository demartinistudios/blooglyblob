# Build cost

Open the [build guide](../build-guide/README.md#build-and-preview) and choose
**Build cost**, or follow **Build cost & shopping list** on Parts & supplies.
The page compares three figures: **Materials used** per robot, and the
**Shopping total** with one black spool or with the guide colors. Its shopping
list shows order quantities, pack prices, line totals and purchase links. Part
cards use the same quotes.

[prices.json](prices.json) is the single source for dated US price quotes and
consumption allowances. The guide combines it with required part quantities and
the selected print plates’ estimated grams. Not included: tools, optional
prints, paint, tax, shipping, handling, import charges and OpenAI API use.

## How the figures are calculated

- **Materials used** charges each quote for the share of its pack one robot
  uses. Shared foam is split by cut area; filament is charged by plate weight.
  For mixed fastener kits, each screw, nut and washer receives an equal share
  of the kit price. This is an allocation estimate, not an individual part's
  selling price or the cash cost of building another robot.
- **Shopping total** rounds demand up to whole retail packs and spools.
  Shared foam is bought once; included accessories add no cost.
- **One black spool** combines all print mass into the catalog’s
  `single_color` PLA quote, so the antenna ball is opaque.
- **Guide colors** buys each filament color as its own spool.
- Each row is rounded to cents, and subtotals and totals add the rounded rows,
  so every figure on the page adds up.
- Both shopping totals assume the tools are owned and no supplies are on hand.
- Fasteners come from the two specified Kadrick kits and the iexcell M3×14
  button-head pack. Each product is bought once for one robot. No flat-head
  pack or separate washer pack is required. The M3 kit contains exactly the
  30 M3×12 screws used, so its other leftovers do not supply another robot.
- A mixed kit's purchase count is the largest of the rounded-up ratios
  `required quantity / quantity in kit` across its components. Total piece
  count alone cannot establish coverage.
- Wire, glue and tape quantities are planning allowances, not measured
  consumption.
- Loose wire is one 10 ft (3.048 m) continuous length of CNC Tech black
  stranded 18 AWG PVC wire from DigiKey. Select Digi-Spool and enter 10 feet;
  the quoted $6.64 is the total at $0.664/ft, not the price of one foot.
  The 2 m material allowance includes spare for extensions and allocates $4.36
  per robot. It is not a measured cut list. Label both ends of each new wire
  with function and destination. Supplied cable assemblies are counted with
  their components; ties, heat-shrink and anchors remain separate purchases.
- Printing in one color and painting is also an option; add the chosen finish.

## Updating prices

To update a price, edit its catalog quote, including the purchase URL and checked
date. `pack_price_usd` and `pack_quantity` use the same `unit` as consumption.
By default, consumption follows the part’s current required quantity. A
`used_quantity` sets a material allowance; `plate_color` selects the current
filament mass. `included_with` identifies an accessory already paid for with
another part. `purchase_group` combines demand sharing one physical pack; its
quotes must agree on price, quantity, unit and source. Group identity is explicit:
a shared product URL alone does not combine distinct filament colors. Multiple
quotes under one item describe its constituent supplies (solder, flux and labels)
or filament colors. `purchase_note` explains shared packs and buying choices in
the shopping list. `alternative_links` offers other sellers without changing the
quoted price; `shopping_notes` labels each category’s pricing source.

Mixed assortments are defined once in `kits`, with `purchase_name`, price,
total `pack_quantity`, `checked_date` and a `components` map of positive whole
counts by part ID. Counts include unused sizes and must sum to the total.
Each supplied item's sole quote is `{"kit": "kit-id"}`; it cannot override
the kit price or inventory. The calculator expands this into component material
rows and one shopping row per kit. Ordinary `purchase_group` still combines
fungible demand such as foam area; it must not represent a mixed assortment.

The catalog date is the default for unchanged quotes. Individual quotes and
kits may carry a newer date; the guide displays the resulting date range and
the date on each purchase. Shipping is excluded, so using fewer sellers does
not produce a claimed shipping saving in these totals.

`make guide-build` recalculates all prices and fails on missing items, invalid
amounts, non-HTTPS links or unpriced filament colors; errors name the part.
There is no second maintained price table.
