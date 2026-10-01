# Build cost

Open the [build guide](../build-guide/README.md#build-and-preview) and choose
**Build cost**, or follow **See price breakdown** on Parts & supplies. The guide
shows the total, category breakdown and individual prices. Part cards show the
same used-material cost and full-pack purchase price.

[prices.json](prices.json) is the single source for dated US price quotes and
consumption allowances. The guide combines it with required part quantities and
the selected print plates’ estimated grams. Tools, optional prints, paint, tax,
shipping, handling, import charges and operating/API costs are excluded.

Pack prices help with shopping; the estimate charges only the material used.
Shared foam is allocated by cut area, included accessories add no separate cost,
and filament is counted once by plate rather than charging for whole spools.
Wire, glue and tape quantities are planning allowances, not measured consumption.
Printing in one color and painting is also an option; add the chosen finish.

To update a price, edit its catalog quote, including the purchase URL and checked
date. `pack_price_usd` and `pack_quantity` use the same `unit` as consumption.
By default, consumption follows the part’s current required quantity. A
`used_quantity` sets a material allowance; `plate_color` selects the current
filament mass. `included_with` identifies an accessory already paid for with
another part. Multiple quotes under one item describe its constituent supplies
(solder, flux and labels) or filament colors, not alternative shopping lists.

`make guide-build` recalculates all prices and fails on missing items, invalid
amounts or unpriced filament colors. There is no second maintained price table.
