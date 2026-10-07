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
- [ASD-STE100 Simplified Technical English](https://www.asd-europe.org/standards-specifications/simplified-technical-english/)
  limits procedural sentences to 20 words, with one instruction per sentence and
  an imperative verb. The [writing standard](#writing-standard) adopts these.
- [ANSI Z535.6](https://www.clarionsafety.com/safety-resources/machinery/understanding-ansi-z535-6-a-guide-to-safety-information-in-product-manuals-and-materials/)
  grades safety messages by signal word and requires each to state the hazard,
  consequence and avoidance beside the step it governs. See
  [Safety messages](#safety-messages).
- [Carroll's minimalism](https://www.instructionaldesign.org/theories/minimalism/)
  favors action-oriented text and support for recognizing and recovering from
  errors. This is the basis for result and recovery lines.
- [NN/g: how users read on the web](https://www.nngroup.com/articles/how-users-read-on-the-web/)
  finds that most readers scan, so the point goes first and extra words go.

## Rules for this guide

These rules cover pictures and page layout. The [writing standard](#writing-standard),
[safety messages](#safety-messages) and [names](#names) below cover the words.

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
   State the general power rule once. Repeat it at power-state transitions
   and specific hazards, not throughout an uninterrupted unpowered assembly
   sequence.
7. **Prepare before mounting.** Test-route when length depends on fit, mark it,
   then solder and heat-shrink off the assembly. Check and cool the work before
   fitting it. Load captive nuts before access disappears; close covers last.
   Glue a nut only when it can fall out or turn before its screw is in, or when
   the design relies on adhesive to hold it. Otherwise load it in the same step
   as its part, right before the screws, and say how to hold it until the
   screw catches.
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
10. **Draw what the builder will see.** A picture shows the state its panel
    leaves, in the same pose and support the actions describe. Do not cram
    several stages into one drawing or use opposed arrows; when order matters,
    add small numbered callouts. Draw tools as tools: a meter probe has a tip
    and a handle, so it cannot be mistaken for a soldered wire. A render that
    contradicts its actions, such as one showing a retired stand, is recorded
    as a picture mismatch until it is re-rendered, and its caption says what it
    shows.
11. **Build steps only.** The guide has no service or repair steps; a builder
    who needs to open the robot reverses the build steps. After the last build
    chapter, the sidebar lists the reference pages under a plain chapter
    heading, Reference, without numbers and without a collapsible menu.
12. **Make detail optional, not the instruction.** Parts lists and references may
    expand on demand. The operation, required dimensions and safety information
    remain visible. Preserve keyboard navigation, readable contrast, image
    descriptions, zoom controls and printable output.

## Writing standard

This standard applies to every step title, action, result line, recovery line,
note, caption and safety message in the guide. It follows ASD-STE100 Simplified
Technical English for sentence length and imperative instructions, ANSI Z535.6
for safety messages, Carroll's minimalism for action-first text with error
recovery, and NN/g reading research for putting the point first.

### Who the guide is written for

Write for a hobbyist who can already solder, strip wire and run commands in a
terminal. Do not teach those skills. Define
only terms that belong to this project: its labels, assemblies, positions and
repeated actions. General terms such as AWG, JST, PLA, GPIO and heat-shrink need
no definition. Define each project term at its first use in the guide and in the
Build notes glossary, using the wording in [Names](#names).

### Limits

Automated checks enforce these limits as errors: `consistency.py check`,
`make guide-build` and `make check` fail on any violation.

| Rule | Limit |
| --- | --- |
| Words in one sentence | 20 or fewer |
| Words in one action (all its sentences) | 35 or fewer |
| Panels in one step | 6 or fewer |
| Actions in one panel | 1 to 3 |
| Instructions in one sentence | 1 |
| Part ID first used in a step | Plain name first, ID in parentheses |
| Banned terms | None of the terms in [Banned terms](#banned-terms) |
| Caption | Does not repeat its panel's action text |

Count words by splitting on spaces. A size or value with its unit counts as
one word when it has no space, such as `M3×6`, `W1/3` or `T1`. A step link
such as `{step:body-lights}` counts as one word. A command counts as one word.
The one-instruction check skips only code spans and software messages in curly
quotes (“…”). A straight " does not exempt text, because it is also an inch mark.

Simple mechanical steps should stay short: one to three panels. An action is one
to three short sentences; a panel holds one to three actions. A step that needs
more than six panels is two steps.

### Sentences

- **One instruction per sentence.** Do not join two instructions with "and",
  "then" or a semicolon. "Start all four screws by hand. Tighten them evenly." is
  two sentences, not one.
- **Verb first.** Start each instruction with an imperative verb: fit, insert,
  solder, label, check. A sentence may open with its location or condition
  instead, followed by the verb: "On the bench, solder…", "At W1, insert…",
  "If the output is short, extend…".
- **Location before action.** Say where before saying what: "At the front
  opening, hold the grille against the base." The reader finds the place, then
  acts.
- **Numbers and units.** Use numerals with units and a space: 11 mm, 5 V,
  1000 µF, 330 Ω. Write fasteners as `M3×6`. Spell out counts from one to nine
  before a fastener size ("four M3×6 screws"); use numerals for 10 and above.
- **Say the number when one is known.** "Strip 11 mm", not "strip a short
  length". Defer to a manufacturer's instructions only when the guide has no
  number, such as an epoxy's cure time. Name the source: "Let the epoxy cure for
  the time on its label."
- **No filler.** Remove "simply", "just", "easily", "carefully", "please",
  "make sure to" and "note that". Keep "gently" and "firmly" when they describe
  the force to use.

### Order within a step

1. **Title.** A verb phrase naming the operation: "Fit the front grille and rear
   vent", not "Vents".
2. **What you need.** Parts, fasteners and tools with quantities, visible at the
   top without expanding anything. Use the plain names from [Names](#names).
3. **Panels.** Each panel is one concrete operation, in the order the builder
   does it (rule 1 above). "Glue the eight board nuts" is one panel, with its
   seat, glue and wait actions inside it. Do not open a step with generic
   technique panels, such as "Seat each nut without glue" or "Glue each nut at
   its edge", ahead of the operations that use them. Teach a technique inside
   the first operation that needs it, then refer back to it. Each panel holds,
   in order: its title, any safety message, its actions, its result line and
   any recovery line. The picture sits beside or directly above them.
4. **Step check.** One line saying what the finished step looks like, or what a
   test shows. Write it as a statement, not an instruction.
5. **Note.** Only a link back or forward to another step ("You fitted these nuts
   in {step:board-cover-nuts}."). Never put an instruction, caution or fact the
   builder needs in a note.

### No pointless ceremony

Cut checks, confirmations, test-fits, reminders and result lines that have no
consequence at that point in the build. A "make sure the bottom cover closes"
check in the middle of the build is ceremony: nothing the builder can do then
depends on it. Say a real constraint once, in the step where it is acted on,
and link back to it rather than repeating it. Keep a check when it catches a
fault while it is still cheap to fix, such as a continuity test before a part
is mounted. Keep every required safety message.

### Physical sense

A rewrite must make physical sense at the bench, not only read well. For each
operation, check:

- which way the assembly lies, and which way each pocket, channel or opening
  faces in that position;
- whether a nut or part can fall out, slide or turn before it is fastened, and
  what holds it until then;
- what each hand is doing, and whether the builder can reach the part (never
  three hands);
- whether an earlier step leaves access for this one, and whether this step
  blocks a later one.

There is no service stand. When the robot must lie down, rest it on something
soft, such as folded towels. Say which way it lies and keep weight off the
head, arms and servos. In powered steps, keep moving parts clear so the robot
cannot tip.

Check against the step's pictures, `hardware/cad/CURRENT-NOTES.md` and the CAD
geometry. CAD is the source of truth for fastening details: screw direction,
nut pockets and which part holds which nut. Question inherited steps: an instruction is not correct because the
old text had it. When the sources do not settle a doubt, keep the current
wording, record the doubt in the work record and flag it to the owner. Do not
carry it over silently or guess a new procedure.

### Result and recovery lines

- **Result line.** After the actions it confirms, on its own line, as a
  statement the builder can see or measure: "The grille sits flat against the
  base." Do not hide the result inside an action sentence.
- **Recovery line.** Where a likely error is known, add "If you see X, do Y"
  directly after the action or result it applies to: "If a screw does not start
  by hand, remove it. Check that its nut is seated." Start recovery lines with
  "If". Do not
  invent a failure that has not been seen or reasoned from the design.

### Captions

Each kind of text has one job, the same in every picture:

- **Inside the picture: labels only.** Part names and IDs, wire colors and
  functions, pins, ports, sizes, quantities, connector size (JST-SM 2.5 mm or
  JST-SH 1.0 mm), a key for numbered marks or colors, and short pointers at one
  spot ("Cut here", "Slide in"). No title, no view line, no sentences, no
  instructions, results or disclaimers.
- **Under the picture: the caption.** Every step picture has one. It says what
  the picture shows and from where: the view direction, what is cut away or
  drawn apart, and what is highlighted. A picture used in several places has
  the same caption everywhere; two different pictures never share one, so the
  caption names what differs (LEFT or RIGHT cable, switch or LED pair). Name a part in full the first time a step
  mentions it, even in a caption.
- **In the actions: everything the builder does or checks.** A caption never
  repeats an action, gives an instruction, disclaims the drawing ("not to
  scale", "illustrative only", "does not show") or carries a fact the builder
  needs. Put needed facts in the action.

The writing check enforces the caption rules (`caption-missing`,
`caption-mismatch`, `caption-shared`, `caption-repeats-action`,
`caption-without-picture`), and
the drawing tests reject sentences inside generated wiring drawings.

## Safety messages

A safety message warns about a hazard in one action. Use one of three levels.
Do not use DANGER.

| Level | Use for | Examples in this build |
| --- | --- | --- |
| WARNING | Fire, electric shock or serious injury | A short circuit or a bypassed fuse; first power-up; mains supply; swallowed magnets |
| CAUTION | Minor or moderate injury | A reversed electrolytic capacitor; a servo moving with fingers near it |
| NOTICE | Damage to parts, with no injury | Cracking thin plastic; forcing a plug; tightening against a nut that is not seated |

Each message has three parts, in this order, in at most three sentences of 20
words or fewer:

1. **Hazard.** What is wrong or dangerous: "A wire from W1 to the light connector
   that skips F2 bypasses the light fuse."
2. **Consequence.** What happens if it is ignored: "A fault could then overheat
   the wires and cause burns or fire."
3. **Avoidance.** An instruction that prevents it: "Connect the light connector
   to W1 only through F2."

Placement and form:

- Put the message in the panel whose action it governs, before that action.
  A message that governs the whole step goes before the first panel.
- Store it as a `safety` entry on the panel or step, with a `level` of
  `warning`, `caution` or `notice` and its `text`. The guide shows the level
  label and styles it; do not type "WARNING" or add bold inside the text.
- Only safety entries carry safety wording. Do not write "warning", "caution",
  "be careful" or "danger" in actions, notes or captions.
- The general power rule and the general soldering, cutting and printing
  precautions live on the Safety and responsibility page. Repeat a power
  warning only at power-state changes and specific hazards (rule 6 above). Do
  not add a generic soldering caution to every soldering action: the audience
  already solders.
- Keep "Stop and unplug if…" instructions at power-up in the action list, as
  recovery lines, with a WARNING before the power-up action.

## Names

Each part, connector, assembly and repeated action has one name. Use it the same
way in actions, titles, captions, diagram labels, part cards and reference pages.

- **Plain name first.** On first use in a step, write the plain name with the ID
  in parentheses: "front microphone grille (FB41)". After that, either the name
  or the ID may be used in the same step.
- **Labels the builder writes follow the same rule.** W1–W4, F2, C1, C2,
  S1, S2, R1, R2 and J1 are written on the parts. Give the plain name at first
  use in a step, such as "input WAGO (W1/3)", then use the label alone. A port
  reference such as W1/3 counts as a use of W1.
- **Write a WAGO port as W1/3.** This means WAGO W1, port 3. Ports are numbered
  1 to 5 from the robot-right end of each WAGO.
- **Sides.** "Robot-left" and "robot-right" are the robot's own sides. Use them
  wherever a side matters. The servo labels LEFT and RIGHT mean robot-left and
  robot-right.
- **Wire, lead and cable.** A wire is one insulated conductor. A lead is a wire
  that comes attached to a component, such as a capacitor leg's wire or the
  fuse holder's loop, or a short purchased cable such as the Pi power lead.
  A cable is two or more wires that run together, usually to one plug.

### Connectors, labels and assemblies

| Thing | Name in text | Label written on it | Replaces |
| --- | --- | --- | --- |
| First JST-SM pair (E10), between the base and the body strand | body light connector; its two halves are the **base half** and the **body half** (the plug on the strand’s input end) | BODY LIGHT | BASE→BODY, H3, BODY, lighting lead |
| Wires from F2, C2 and S1 D5 (through R2) to the base half | base-half wires (+5 V, GND, DATA) | — | H3 +5 V, H3 return, H3 DATA |
| Second JST-SM pair (E10), between the body and the head | head light connector; its two halves are the **body half** and the **head half** | HEAD LIGHT | HEAD (as a connector), HEAD plug, HEAD latch |
| The strand’s three wires after light 5, with any extension, running up to the head light connector | head light cable | — | three-wire HEAD lighting cable, head power pair |
| Half of the cut JST-SH cable (E11), from the head half to the first eye’s IN | eye input lead | — | eye lead, 5755 lead |
| Other half of the cut JST-SH cable (E11), from the second eye’s OUT to the mouth pads | mouth lead | — | mouth leads, mouth power leads |
| Head half of the head light connector, the eye input lead, the eye cable and the mouth lead | head harness | — | mouth board and harness |
| Head shelf (P08) with the head horn adapter (P14) and its horn screwed on | head shelf assembly | — | — |
| Micro-USB lead (E22) from W1 and W3 to the Pi | Pi power lead | PI POWER | H2 |
| Servo cables | left arm servo cable, right arm servo cable, head servo cable | LEFT, RIGHT, HEAD | HEAD cable (for the servo) |
| Panel jack (E18) | power jack (J1); its contacts are the **center** and the **sleeve** | J1 | inlet, panel jack |
| WAGO W1 | input WAGO (W1) | W1 | — |
| WAGO W2 | servo power WAGO (W2) | W2 | — |
| WAGO W3 | ground WAGO (W3) | W3 | — |
| WAGO W4 | servo ground WAGO (W4) | W4 | — |
| F2 fuse and holder (E07) | light fuse (F2), T1 A | F2 | — |
| C1 (E08) | servo capacitor (C1) | C1 | — |
| C2 (E08) | light capacitor (C2) | C2 | — |
| S1, S2 (E15) | level shifter (S1), level shifter (S2) | S1, S2 | Pixel Shifter (except in the part card) |
| R1 (1 kΩ) | button LED resistor (R1) | — | — |
| R2 (330 Ω) | data resistor (R2) | — | — |
| One LED bead on the body strand (E05) | pebble | — | — |
| A place in the lighting data chain: body 0–5, eyes 6–7, mouth 8–15 | light 0 to light 15 | — | pixel (except in software output) |
| FB01 and everything mounted in it | base | — | enclosure, electronics enclosure |
| Central hole in the base's top wall, between the two frame screws, where the servo cables and body light connector enter | harness opening | — | central opening, central wire hole |

Retired names must not appear in guide text, captions, diagram labels, part
cards or generator labels once the rewrite is complete.

### Repeated actions

| Name | Meaning (glossary wording) | Replaces |
| --- | --- | --- |
| test-route | Run a wire along its final path without fixing or soldering it, to find its length. Mark it, then return to the bench. | dry-route |
| test-fit | Fit parts without glue or final tightening to check the fit, then remove them. | dry-fit |
| insert (a wire into a WAGO) | Strip 11 mm, push the bare wire fully into the port and close the lever. | land |
| connect (a wire to a board) | Fasten the wire in the named terminal, such as S1 D5, or push a jumper lead onto the named Pi pin. | land |
| fit position | The servo position set by `make pi-servo-fit`: head facing forward, arms hanging straight down. The robot also returns here when the application starts. | fit pose, rest pose |
| wire bundle | Two or more wires tied together along one path. Always say which wires. | bundle (alone) |
| seat | Push a plug or part fully home until it latches or sits flat. | — |

"Pull-check" and "dress" have no replacement term. Write the action plainly:
"Pull gently on the wire. It must stay in the port." and "Bend the USB cable so
the cover closes without pressing on it."

### Printed parts

Use these names in steps. Where the name differs from the current part card,
the part card changes to match.

| ID | Name in steps | Current part-card name |
| --- | --- | --- |
| A04 | antenna coil | same |
| A05 | antenna ball | same |
| AR01 | robot-left upper arm | same |
| AR02 | robot-left forearm | same |
| AR03 | robot-left relaxed hand | same |
| AR04 | robot-right upper arm | same |
| AR05 | robot-right forearm | same |
| AR06 | robot-right relaxed hand | same |
| AR07 | robot-left pointing hand (optional) | Pointing hand, robot-left (optional) |
| AR08 | robot-left shoulder cover | same |
| AR09 | robot-right shoulder cover | same |
| B01 | robot-left rear belt link | same |
| B02 | front belt link | same |
| B03 | belt buckle | same |
| B04 | robot-right rear belt link | same |
| B09 | belt pin | same |
| FB01 | base | Electronics enclosure |
| FB02 | bottom cover | same |
| FB03 | rear vent | same |
| FB19 | side speaker grille | same |
| FB20 | button insert | same |
| FB21 | power jack plate | Power inlet plate |
| FB24 | audio cradle | same |
| FB32 | audio cradle lid | same |
| FB41 | front microphone grille | same |
| GS01 | robot-left head strap | Robot-left gray head strap |
| GS02 | robot-right head strap | Robot-right gray head strap |
| GS03 | rear head strap | Rear gray head strap |
| GS11 | robot-right eye housing | Robot-right copper goggle housing |
| GS12 | robot-left eye housing | Robot-left copper goggle housing |
| GS20 | head shell | same |
| P01 | foam collar | Round foam collar |
| P02 | frame upright | same |
| P03 | shoulder-servo bracket | same |
| P04 | head-servo bracket | same |
| P06 | eye LED cassette | same |
| P08 | head shelf | Rotating head shelf |
| P09 | rear seam backing | same |
| P10 | rear seam cover | same |
| P11 | front body-light bracket | same |
| P12 | rear body-light bracket | Rear body-light bracket and seam backing |
| P13 | body wire guide | same |
| P14 | head horn adapter | same |
| P30 | mouth LED cassette | same |
| P31 | mouth light separator | same |
| P34 | curved backpack carrier | same |
| P35 | backpack shell | same |
| P36 | backpack tank | same |
| P37 | nozzle plug | same |
| P38 | robot-left backpack elbow | same |
| P39 | robot-right backpack elbow | same |
| P40 | backpack top band | same |

### Banned terms

Automated checks flag these in guide text, captions and part cards. Replace
each with the name or wording given.

| Term | Use instead |
| --- | --- |
| land, landed, landing (a wire) | insert (into a WAGO port) or connect (to a terminal or pin) |
| dry-route, dry-routing | test-route |
| dry-fit, dry-fitting | test-fit |
| pull-check | "Pull gently on the wire. It must stay in the port." |
| fit pose, rest pose | fit position |
| dress | a plain instruction saying where the cable goes |
| enclosure | base |
| inlet, panel jack | power jack (J1) |
| central opening, central wire hole | harness opening |
| BASE→BODY, H3, BODY (as a connector) | body light connector, base half, body half |
| HEAD (as a connector), HEAD tails | head light connector, head light cable |
| H2 | Pi power lead |
| pigtail | the named lead: eye input lead, mouth lead |
| head power pair, input harness | retired with the daisy-chained lights: name the head light cable, the body half or the base-half wires |
| service stand, stand board, stand blocks | folded towels; say which way the robot lies |
| simply, just, easily, carefully, please, make sure, note that | delete |
| warning, caution, be careful, danger (outside a safety entry, except when quoting a message the software shows) | a safety entry |
| not to scale, illustrative, does not show (in a caption) | delete |

## Worked examples

These show the target form on two steps, written before the chapter rewrites.
The guide's own steps are now the reference for content. Each numbered line
here is one sentence; in the guide data, one to three sentences make one action.

### Example 1: Fit the front grille and rear vent (mechanical)

The current title, "Fit the front and rear vents", calls FB41 a vent. Its name
is front microphone grille, so the title changes.

The front nuts are loaded in this step, right before their screws, and are not
glued. Each front channel is open on the inside of the base, so a screw would
push a loose nut out. The nut only needs holding until its screw catches. After
that, the screw clamps the wall between the grille and the nut. A fingertip
holds it, so it needs no glue. The rear vent nuts are not glued either. Each is
placed right before its screw and held with a fingertip through the open
bottom until the screw catches.

**You need:** base (FB01) · front microphone grille (FB41) · rear vent (FB03) ·
four M3×6 screws · four M3×12 screws · eight M3 nuts · small drivers and hex
keys (T05)

**Panel 1: Find the two openings**

1. Place the base (FB01) upside down, with its open bottom facing up.
2. Find the front opening. The front microphone grille (FB41) fits here.
3. Find the rear opening. The rear vent (FB03) fits here.

*Caption:* View through the open bottom, with the front at the lower left.

**Panel 2: Load the four front grille nuts**

1. Find the four nut channels on the inside of the front wall, around the
   opening. Place an M3 nut flat against the wall in each channel.
2. Slide each nut toward the top of the base until it stops. Do not force it.
   Do not glue these nuts.

*Result:* Each nut rests at the end of its channel, over its screw hole.

*Caption:* Drawn upright: the arrow points toward the top of the base.

**Panel 3: Start the first grille screw**

> **NOTICE** The plastic behind the front nuts is thin. Too much force can
> crack it. Support the plastic behind the nuts while you work.

1. At the front opening, hold the grille against the outside of the base. Put
   one M3×6 screw through a grille hole. Use no washers.
2. With your other hand, press that hole's nut against the wall from inside.
   Turn the screw by hand until it catches.

*Caption:* Front wall cut away. Arrows show each screw's path.

**Panel 4: Fasten the front microphone grille**

1. Repeat for the other three holes, one screw at a time. Tighten all four
   screws evenly.

*Result:* The grille sits flat against the base.

*Recovery:* If a screw does not start by hand, remove it. Check that its nut is
seated.

**Panel 5: Hold a rear vent nut in its pocket**

1. Through the open bottom, place an M3 nut in one of the four pockets around
   the rear opening. Match its flats to the pocket. Hold it there with a
   fingertip. Do not glue it.

*Caption:* One rear vent pocket, before and after its nut is seated.

**Panel 6: Fit the rear vent**

1. With your other hand, hold the rear vent against the outside of the base.
   Put an M3×12 screw through the vent into that nut. Use no washer. Turn it by
   hand until it catches.
2. Repeat for the other three pockets, one nut at a time. Tighten all four
   screws evenly. Leave the bottom of the base open.

*Result:* The vent sits flat against the base.

*Caption:* Rear wall cut away.

**Check:** Both parts sit flat. Each nut stays seated and the plastic around it
is not cracked.

### Example 2: Wire the servo power and capacitor (wiring)

**You need:** capacitor (E08), 1000 µF, 10 V · 18 AWG wire (C05) ·
heat-shrink (C12) · solder, flux and wire labels (C14) · cable ties (C07) ·
adhesive tie squares (C17) · flush cutters (T01) · soldering iron (T02) · wire stripper (T04) ·
heat-shrink tool (T09)

**Panel 1: Cut and strip the servo feed**

1. Test-route a red 18 AWG wire from the input WAGO (W1/3) to the servo power
   WAGO (W2/1). Mark where it reaches without tension.
2. Cut the wire at the mark. Strip 11 mm from each end.

*Caption:* The servo feed wire, stripped at both ends.

**Panel 2: Connect the servo feed**

1. Insert one end into W1/3. Insert the other end into W2/1. Close both levers.
2. Keep W2/2 to W2/4 free for the three servos.

*Caption:* Wire-entry faces of W1 and W2.

**Panel 3: Prepare and connect the servo capacitor**

> **CAUTION** The servo capacitor (C1) is polarized. Connected backwards, it
> can overheat and vent when powered. Connect its striped negative leg to the
> ground WAGO (W3/4).

1. Label one 1000 µF, 10 V capacitor (E08) C1. The stripe marks its negative
   leg. On the bench, solder an 18 AWG wire to each leg. Mark the negative wire.
2. Cover each leg and its joint with its own heat-shrink. Lay C1 roughly where
   the layout detail shows. Cut each wire to reach its port.
3. Insert the positive wire into W2/5. Insert the negative wire into W3/4.
   Bend the wires gently at the rubber-seal end. Keep the vent end uncovered.

*Caption:* C1 with its sleeved wires, and the wire-entry faces of W2 and W3.

**Panel 4: Tie C1 down**

1. Choose a flat face beside C1. Prepare it as the square’s instructions say.
   Stick an adhesive tie square (C17) there.
2. Tie C1’s body to the square with a cable tie (C07). Keep the tie off the
   rubber-seal end and the vent end.
3. Tighten the tie only enough to stop sliding. Trim the tail. C1 is held by
   its tie, not by its wires.

*Caption:* Side view of a tie square holding a capacitor.

**Check:** One red 18 AWG wire joins W1/3 to W2/1. C1 polarity is correct.
Its two insulated wires are separate, and its body is tied down.

### How the examples meet the limits

| Limit | Example 1 | Example 2 |
| --- | --- | --- |
| Longest sentence (20 or fewer words) | 18 | 17 |
| Longest action (35 or fewer words) | 34 | 30 |
| Panels (6 or fewer) | 6 | 4 |
| IDs and labels named on first use | FB01, FB41, FB03 | E08, C1, W1, W2, W3 |
| Banned terms | none | none |
| Captions repeating an action | none | none |

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
