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
- **Shopping total** rounds demand up to whole retail packs and spools.
  Shared foam is bought once; included accessories add no cost.
- **One black spool** combines all print mass into the catalog’s
  `single_color` PLA quote, so the antenna ball is opaque.
- **Guide colors** buys each filament color as its own spool.
- Each row is rounded to cents, and subtotals and totals add the rounded rows,
  so every figure on the page adds up.
- Both shopping totals assume the tools are owned and no supplies are on hand.
- Screws and nuts are priced individually; a generic assortment is not
  substituted for the specified sizes and head shapes.
- Wire, glue and tape quantities are planning allowances, not measured
  consumption.
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

`make guide-build` recalculates all prices and fails on missing items, invalid
amounts, non-HTTPS links or unpriced filament colors; errors name the part.
There is no second maintained price table.
