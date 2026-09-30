# Cold-reader test protocol

A cold read tests whether a new builder can follow the guide alone. One
participant builds from the guide while one observer watches and records. The
observer does not help. Each place the participant stops, re-reads, goes wrong
or asks a question is a finding against a step and a panel.

## Participant

Choose a hobbyist who matches the guide's audience:

- They can solder, strip wire and run commands in a terminal.
- They can take basic multimeter readings, such as continuity and DC voltage.
- They have not seen this robot, this guide or its source files.
- They have not helped anyone build it.

A participant is cold only once for each chapter. After they read a chapter,
their later findings on it do not count as a cold read. Use a new participant
to test a chapter again.

## Before the session

1. Pick the chapters for the session. Start at the first chapter the
   participant has not done. Plan to stop at a chapter end.
2. Record the guide revision under test: the Git commit, or the date of the
   published site.
3. Build and open the guide. Use the preview in the [authoring guide](README.md)
   or the published site.
4. Open the guide in a fresh browser profile or a private window, so no saved
   progress or parts ticks show.
5. Lay out the parts, supplies and tools that the chosen chapters list. Put
   them in their bags and boxes, not sorted by step.
6. Supply printed parts from earlier prints when the session is not about
   printing. The prints take about 39 hours, so start them well before.
7. For the Pi software chapter, provide a network and a computer with a
   terminal. Provide an OpenAI API key on a card if the participant has none.
   Revoke that key after the session.
8. Check the bench: ventilation for soldering, a fire-safe iron stand, eye
   protection and a first-aid kit.
9. Copy the [findings template](#findings-template) into a new file for this
   session. Use one file per session.
10. Get the participant's consent for notes and any photos. Do not record
    their name in the findings file; use a code such as P1.

The observer needs:

- This protocol and the findings file.
- A clock or timer.
- The guide open on a second screen, so they can see the step and panel the
  participant is on.
- A phone camera, used only with consent, to photograph wrong actions.

## Start the session

Read this to the participant:

> Build the robot from this guide as if you were alone at home. I will watch
> and take notes. I will not answer questions or explain anything, because I
> am testing the guide, not you. If you would normally search the web or open
> a datasheet, do so. When you pause, please say out loud what you are looking
> for. I will stop you only if something is unsafe.

Then start the clock and say nothing more.

## Observe in silence

- Do not help, explain, point or nod. Do not react to a wrong action.
- If the participant asks a question, reply: "What would you do if I were not
  here?" Record the question.
- If the participant is stuck for 10 minutes, ask whether they want to stop
  the step. If they do, give the smallest hint that lets them continue. Record
  it as an assist. That step no longer counts as a cold read.
- Let wrong actions happen. Record them and let the participant find them. A
  wrong action that the guide lets through is the most useful finding.

### When to intervene

Intervene only to prevent injury, fire or damage to a part that would end the
session. Say "Stop, please," and explain only the hazard. Examples:

- A hot iron or a blade near a hand, hair or cable insulation.
- Power about to be applied with bare conductors touching, or with reversed
  polarity at a supply, fuse, capacitor or board.
- Fingers near a moving servo or arm during a powered step.
- Solvent or epoxy use without ventilation.

Record each intervention as a safety stop, with what the participant was about
to do. Then let them continue from where they stopped.

## Chapters in order

Run the chapters in the guide's order. Do not skip ahead or reorder them, even
between sessions.

1. Prepare
2. Print
3. Base hardware
4. Pi software
5. Base boards and controls
6. Base wiring
7. Light test
8. Frame and servos
9. Head
10. Body
11. Arms
12. Backpack and belt
13. Final wiring
14. First power-up
15. Head and arm mounting
16. Close up and test

Test the Service steps in a separate session, on a finished robot. Start the
participant at "Before you start" in the first session. Start each later
session at the first step not yet done.

## What to record

Record each event against its step and panel:

- **Step:** the step number on the page and the step ID in the address bar,
  after `#step-`. Example: `27 servo-fuse-capacitor`. Service steps have no
  number; use their ID.
- **Panel:** the number at the top left of the panel. For the parts list at
  the top of a step, write `top`. For the safety box, the step note or the
  "Ready to continue" box, write `safety`, `note` or `check`.

Record these event types:

| Type | Record it when the participant |
| --- | --- |
| Hesitation | Stops for 30 seconds or more before acting. |
| Re-read | Scrolls back or reads a panel, caption or picture again. |
| Wrong action | Does something other than what the step intends, even if they later fix it. |
| Question | Asks something aloud, or says they are unsure. |
| Lookup | Leaves the step to find something: parts page, reference page, datasheet or web search. |
| Assist | Receives a hint from the observer. |
| Safety stop | Is stopped by the observer. |

Write what you saw, not why you think it happened. Quote the participant's
words where you can. Note the time of each event. Also record the start and end
time of each chapter, and any breaks for curing or printing.

## Findings template

Copy this section into a new file for each session. Name the file after the
date and participant code, for example `2026-10-04-cold-read-P1.md`. Keep
filled-in files with your private build notes, not in the repository.

```markdown
# Cold read: <date>, participant <code>

- Session type: cold read | owner bench walk-through
- Guide revision: <commit or published date>
- Observer: <name>
- Participant profile check: solders yes/no; terminal yes/no; meter yes/no;
  has not seen the robot yes/no
- Chapters covered: <first chapter> to <last chapter>
- Device and screen: <for example, laptop 14 in, phone 360 px>
- Start and end: <times>; breaks: <times and reason>

## Events

| # | Time | Step (number and ID) | Panel | Type | What happened | Participant's words | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | |

Severity: 1 = safety stop, or a part damaged or scrapped; 2 = wrong action
found later, or an assist; 3 = hesitation, re-read, lookup or wrong action
fixed at once; 4 = question or comment with no effect on the build.

## Triage (after the session)

| # | Cause in the guide | Proposed change | Review surface | Decision |
| --- | --- | --- | --- | --- |
| 1 | | | | fix / no change / bench check |

## Summary

- Chapters finished without an assist: <list>
- Severity 1 and 2 events: <count>
- Steps with three or more events: <list>
```

## From findings to guide changes

Findings change the guide only through the normal review process. Do not edit
the guide during a session.

1. Triage every event in the session's findings file. Decide: fix, no change,
   or bench check. A finding can point to a fact that needs a physical check,
   such as a cable length.
2. Make each fix by the [instruction design guidance](INSTRUCTION-DESIGN.md).
   Follow "Review an input or guide change" in the [authoring guide](README.md).
3. Set each affected surface in [review-status.json](review-status.json) to
   `pending`, with a one-line reason.
4. Run `make check`.
5. Review the changed surfaces again. Set them to `verified` with the revision,
   reviewer and evidence. Add concise public evidence to [REVIEW.md](REVIEW.md).
   Do not put participant names or identifying details in public files.

Test a fixed chapter again with a new participant before you count the fix as
confirmed.

## Owner bench walk-through

The owner, or anyone who knows the robot, can walk through the guide at the
bench with the same template. Set "Session type" to "owner bench
walk-through". This checks physical facts: fit, cable reach, tool access and
whether each procedure works. It is not a cold read. The owner knows the
intended result and fills gaps without noticing. Do not count a walk-through as
evidence that a new builder can follow the guide.
