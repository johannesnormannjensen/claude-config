---
name: crew-ticket
description: Use when the owner describes an idea, a batch of ideas, or a design pasted from another chat, or says "add a ticket", "for later", or "/crew-ticket". Also when they answer your numbered questions ("1. yes 2. …"). Relay the idea, ask the questions that close its gaps, write the ticket, and stop. Do not launch a crew or a preview.
---

# /crew-ticket: from idea to a ticket a crew can run

The goal is a ticket a crew can pick up cold. Every choice it would otherwise have to guess is
decided, or marked open on purpose. Project specifics (the tracker, extra question topics, the
workflow values) come from `.claude/crew.md`.

## 1. Ground it (silent and cheap)
Grep for the code the idea touches: what exists today, the constants, the module names, what
nearby tickets already cover. Do this before asking anything, so the questions are about real
gaps and not things the code already answers.

Clash check (always): read every open ticket in the tracker, plus any crew branch still running,
and list each one that touches the same files, systems, rules or user-facing behaviour. Each
one is a duplicate (fold the idea into it), a conflict (a rule one of them must break: ask the
owner), or an order dependency (this waits on it, or it on this). Report them in step 2 even
when there are none ("no clashes with open tickets").

## 2. Relay it back
In your own words, a few short paragraphs:
- what changes for whoever uses the result (the people crew.md's Project describes: players,
  visitors, API callers, operators of the infrastructure, other developers), and why the owner wants it
- how it fits the current code ("today X does Y in `path`")
- anything that clashes with an existing rule, system or ticket

## 3. Ask (numbered prose, never the AskUserQuestion tool)
At most 5 questions per round, each with your default ("My default is …"), so the owner can
just say "yes". Ask only where the answer would change what the crew builds. Pick from these,
plus the topics under "Tickets → Questions" in `.claude/crew.md`:

- **Experience:** what it looks, reads or feels like to the user; the moment it should land
- **Scope:** replace or add to what exists; what is explicitly out of scope
- **Edges:** empty, huge, invalid or concurrent input; errors; the end of the line
- **Existing systems:** what keeps working, what must change, which rules break
- **Compatibility:** stored data, public APIs, file formats, old clients or old source code
- **Numbers:** sizes, limits, speeds, rates, budgets
- **Scale and performance:** large inputs, many users or entities, cost at the limit
- **Order:** which tickets it waits on or must come before, and why
- **Done:** what test, and what "Show it" artifact from `.claude/crew.md` (a screenshot, sample
  output), would convince the owner
- **Research:** references to study first (crew.md names some)
- **Workflow:** which value from the "Workflow field" section of `.claude/crew.md` this ticket
  gets. Default to the one that section marks as default. Prefer the preview value when the
  result's look or wording is still open and crew.md's "Show it" is not `none`, and the
  full-research value when the ticket says to study a reference first. Skip this question when
  `.claude/crew.md` has no "Workflow field" section.

Repeat until the owner confirms. An answer like "open for debate, not this scope" goes into
the ticket as an out-of-scope note, not another question. If the owner says "just write it
down", skip this step and mark the open points as defaults. A numbered answer here is still
this skill. It is not a request to start work.

## 4. Write it
The tracker's location is under "Tickets" in `.claude/crew.md`. Without one, ask once. With a remote,
pull first. Take the next free number from the tracker as it is now (other sessions add tickets too). One entry:

- **Title** (owner date, one workflow value, after/before which tickets). Copy only the value
  from the "Workflow field" section, written as `workflow: preview`, `workflow: fast`,
  `workflow: crew:quick`, or `workflow: crew:full`. Do not copy the explanation after it. That
  field wins over a conflicting sentence in the body.
- what and why, in the owner's terms, then the confirmed decisions as concrete rules
- pointers: files and constants the crew starts from
- out of scope and open ideas
- done: the evidence that proves it

Keep it dense and plain. Commit only the tracker file, and push if there is a remote.

## 5. Report
Give the ticket number, the workflow value you wrote, its place in the queue, and whether it
can start now or what it waits on. Then stop. Do not launch the workflow.
