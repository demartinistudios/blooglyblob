# Build cost

Open the [build guide](../build-guide/README.md#build-and-preview) and choose
**Build cost**, or follow **Costs & shopping list** on Parts & supplies. Compare
materials used with upfront supplies for one filament color or the guide’s
colors. The shopping list shows order quantities, pack/spool prices and line
totals. Part cards use the same quotes.

[prices.json](prices.json) is the single source for dated US price quotes and
consumption allowances. The guide combines it with required part quantities and
the selected print plates’ estimated grams. Tools, optional prints, paint, tax,
shipping, handling, import charges and operating/API costs are excluded.

The materials-used estimate allocates shared foam by cut area and filament by
plate weight. The two supply estimates round demand up to whole retail packs
and spools. Shared foam is purchased once; included accessories add no separate
cost. The single-color estimate combines all print mass into the catalog’s
`single_color` PLA quote, including an opaque antenna ball. The guide-color
estimate buys each filament color separately. Both assume the tools are owned
and no supplies are on hand. Screw/nut sources sell individual quantities; a
generic assortment is not substituted for specified sizes and head shapes.
Wire, glue and tape quantities are planning allowances, not measured consumption.
Printing in one color and painting is also an option; add the chosen finish.

To update a price, edit its catalog quote, including the purchase URL and checked
date. `pack_price_usd` and `pack_quantity` use the same `unit` as consumption.
By default, consumption follows the part’s current required quantity. A
`used_quantity` sets a material allowance; `plate_color` selects the current
filament mass. `included_with` identifies an accessory already paid for with
another part. `purchase_group` combines demand sharing one physical pack; its
quotes must agree on price, quantity, unit and source. Group identity is explicit:
a shared product URL alone does not combine distinct filament colors. Multiple
quotes under one item describe its constituent supplies (solder, flux and labels)
or filament colors. `purchase_note` explains shared packs in the shopping list.
`alternative_links` offers other sellers without changing the quoted price; label
the pricing source clearly when displaying alternatives.

`make guide-build` recalculates all prices and fails on missing items, invalid
amounts or unpriced filament colors. There is no second maintained price table.
