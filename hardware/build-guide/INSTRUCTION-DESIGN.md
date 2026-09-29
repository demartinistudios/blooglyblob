# Designing the assembly instructions

Use this when authoring or reviewing the public guide. The builder should be able
to identify the part, see the movement or connection, perform it, and check the
result without reconstructing the design process. Keep research and review notes
out of the public steps.

## What the references contribute

Reviewed September 27, 2026. These are sources of guidance, not evidence that
BlooglyBlob has passed a physical build test.

- [iFixit: writing guides](https://www.ifixit.com/Info/Writing_Guides) recommends
  pictures and text that complement one another, consistent object orientation,
  direct language, and little background explanation. It cautions against vague
  part names and excessive annotations. Apply those lessons to CAD illustrations
  as well as photos.
- [iFixit: guide steps](https://www.ifixit.com/Help/Guide_Steps) connects image
  markers to the corresponding instructions. Our equivalent is a short label,
  visible destination and movement arrow, with a matching part name in the text.
- [Microsoft: step-by-step instructions](https://learn.microsoft.com/en-us/style-guide/procedures-instructions/writing-step-by-step-instructions)
  recommends concise action headings, numbered instructions, stating the location
  before the action, and avoiding introductions that repeat the heading. It
  permits closely related short actions to stay together.
- [LEGO Builder](https://www.lego.com/en-us/service/help-topics/article/lego-builder-app-3d-building-instructions)
  supports zooming and rotating models to inspect assembly. We retain enlargement
  for detailed inspection; the normal illustration must still explain the action.
  This guide does not implement interactive CAD rotation.
- [IKEA VIDGA instructions](https://www.ikea.com/us/en/assembly_instructions/vidga-corner-piece-single-track-included-ceiling-hardware-white__AA-2265275-2-100.pdf)
  provide a compact example of numbered assembly drawings with insertion,
  rotation and locking indications. We borrow that action-focused presentation,
  not a text-free rule: wiring polarity, screw sizes and tests still need words.
- [NN/g: instructional overlays](https://www.nngroup.com/articles/mobile-instructional-overlay/)
  describes the burden of dense tips, memorizing instructions away from their
  context, and text that refers to unmarked objects. This is interface research;
  applying its proximity and focus lessons to physical assembly is our inference.

## Rules for this guide

1. **One operation per panel.** A heading states the action, not just the component
   name. A first screw and its identical repetitions may share a panel. A different
   tool, viewpoint or assembly state usually needs another panel.
2. **Show what changes.** Show the actual part and its mating feature. Use an
   arrow for insertion or motion, a leader for identification, and an inset for
   a hidden interface. Do not add a decorative arrow to a finished overview.
3. **Preserve orientation.** Keep front/left/right consistent across neighboring
   views. Say when to turn the assembly. Use a local locator only when needed;
   unrelated parts should not compete with the active joint.
4. **Make the fastening path visible.** Show the screw head side, washer location,
   receiving nut and access direction. Use accepted CAD for printed surfaces.
   Nominal hardware may clarify the joint but must match the verified size and
   axis. Show recognizable threads, recessed drives, nut bores and plausible
   material colors. Do not use plain yellow cylinders or blocks as hardware.
   Purchased-part recognition models must retain verified placement and dimensions;
   they do not establish fit or prescribe wire routing. Do not substitute boxes,
   a circuit schematic or a product picture for fastening instructions.
5. **Keep words beside their subject.** Put action text and necessary notes in the
   same panel as its image. At narrow widths, stack them immediately together.
   Avoid repeated full paragraphs inside the image and in the page. Use plain
   body text for necessary details; no quote-style borders, indented notes or
   repeated captions. Put required information directly in the action when possible.
6. **Write only what helps the next action.** Keep identity, quantity, dimensions,
   polarity, order, access constraints and the check for success. Remove internal
   coordinates, render commentary, revision stories and duplicated descriptions.
   Essential cautions belong before the action they affect, never in hidden help.
   State the general power rule once. Repeat it at power-state transitions,
   specific hazards and standalone service entry points, not throughout an
   uninterrupted unpowered assembly sequence.
7. **Prepare before mounting.** Dry-route when length depends on fit, mark it,
   then solder and heat-shrink off the assembly. Check and cool the work before
   fitting it. Load captive nuts before access disappears; close covers last.
8. **Use compact framing, not tiny labels.** Show the local joint at a useful
   scale. Remove blank canvas and repeated figures before reducing size. Dense
   electrical diagrams need extra room; if their labels no longer read, split
   the diagram instead of relying on the enlarge button for essential facts.
9. **Use diagrams suited to the action.** Mechanical assembly needs geometry;
   electrical connections need named terminals and polarity; commands need
   readable code and the expected result. Do not invent a physical picture for
   a software-only action just to fill a template. Wiring actions should show both
   physical endpoints and a continuous wire between them. Distinguish an insulated
   wire crossing from a soldered branch, show the actual wire-entry face, and keep
   connector contact order separate from illustrative wire colors. Pair a complete
   connection view with a close-up when stripping, soldering or clamping needs one.
10. **Make detail optional, not the instruction.** Parts lists and references may
    expand on demand. The operation, required dimensions and safety information
    remain visible. Preserve keyboard navigation, readable contrast, image
    descriptions, zoom controls and printable output.

## Builder checks and design validation

Write the assembly sequence for someone reproducing the specified design. Keep
checks of their work: correct parts and orientation, polarity/continuity,
insulated joints, connector seating, cable clearance, software startup and
expected light/sound/movement. Do not ask builders to qualify current budgets,
fuse margins, thermal performance or endurance, or buy instruments for those
tests. Maintain that engineering evidence in hardware records. Removing those
tasks from the guide is not evidence that design qualification has happened.
Troubleshooting may provide targeted measurements when a fault occurs.

## Common failure patterns

| Failure | Why it fails | Fix |
| --- | --- | --- |
| Large completed-model render | Builder has to infer what changed | Show the joint and insertion path |
| Wrong related image | Familiar component disguises missing instruction | Match the pictured operation exactly |
| Many arrows or labels | No clear next action | Separate operations; keep only relevant pointers |
| Long image above a long paragraph | Constant scrolling separates explanation from target | Compact framing and adjacent copy |
| Text baked into huge image margins | Scaling makes either the page or the text unusable | Put prose in HTML; keep only diagram labels |
| Unannounced viewpoint change | Left/right and screw direction become ambiguous | Keep the viewpoint or explicitly show the turn |
| “Fit as shown” with no fastening detail | Omits the decision the builder needs | Show entry side, stack and receiving feature |
| Preparation after installation | Forces hot tools near plastic or needless disassembly | Prepare/check the loose subassembly first |
| Automatic “every image has an arrow” check | An arrow can still point to the wrong thing | Review the physical meaning against sources |

## Review at the bench and in the browser

For each changed panel, ask: which part, which face, which movement, which
fastener, and what tells the builder it is done? Verify that the drawing answers
those questions and that earlier steps leave access for this one. Use the
existing guide work record for specific findings and unresolved items.

Check desktop, tablet and 360 px phone layouts. Inspect normal-size labels as
well as enlarged images; inspect long electrical and software steps separately.
Check print output, no horizontal overflow, and no clipped commands or warnings.
Measure representative page heights before and after layout changes, but never
optimize scrolling at the expense of legibility. Automated checks cover routes,
assets and layout bounds; physical meaning still requires visual review and a
real build remains separate evidence.

For an illustration audit, inventory every authored image and generated plate
preview. Inspect contact sheets first, then enlarge suspect details. Trace every
cable to its connector or strain relief, every terminal tab to its component,
and every fastener along its receiving axis. Check projected heights as well as
plan coordinates: endpoints can share an x/y location yet look disconnected.
Check drawing order for objects hiding wires or filling through-holes. Compare
an action image with its text: a bare recess is not an installation illustration
of the magnet or horn that belongs there. Composite transparent images on the
actual page background before reporting missing or low-contrast geometry.
Record coverage, confirmed defects, corrections and uncertain details in the
existing guide record; a visual audit does not qualify physical fit.
