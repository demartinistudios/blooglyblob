# Hardware changes and current guidance

The [current design](cad/CURRENT-DESIGN.md), [technical notes](cad/CURRENT-NOTES.md)
and [print procedure](printing/current/README.md) describe the selected hardware
and its limitations. Exact inputs and hashes live in the
[registry](cad/design-control/registry.json) and current input lock.

Keep public change descriptions concise: affected part IDs, resulting behavior,
required compatibility changes and known limitations. Detailed trial histories,
printer jobs and agent work records stay in ignored local folders. A metadata or
workflow change does not establish physical qualification.

The public print-project [privacy proof](printing/recipes/project-privacy.json)
records removal of personal account metadata without changing geometry or
settings. Source comparisons, guide review and physical qualification remain
separate checks; see the [release checklist](../docs/release/checklist.md).
