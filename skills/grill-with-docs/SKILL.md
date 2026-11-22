---
name: grill-with-docs
description: Use when the owner wants to think a design, concept or naming question through without filing a ticket ("grill me", "/grill-with-docs", "what do we mean by X", "let's settle how Y works"). Interviews in rounds until every branch is decided, and writes the glossary and decision records as terms and decisions settle. For an idea that should become a ticket, use crew-ticket.
---

# /grill-with-docs: settle a design and write down its words

Adapted from mattpocock/skills (`grilling`, `domain-modeling`; MIT).

The goal is a shared understanding, with its vocabulary and hard decisions saved where the next
agent will read them. Nothing gets built in this skill.

## Where things go
The project's AGENTS.md routes glossaries and decision records. Read the glossary for the area
before the first round. Nothing routed: a root `GLOSSARY.md` and `docs/adr/`, created only when
the first entry is ready.

## Rounds
Ask as crew-ticket step 3 does: numbered prose, a default per question, at most 5, numbering
that runs on across rounds, and only questions whose prerequisites are settled. Facts are yours
to find. Between questions, do four things:

- **Hold the words to the glossary.** A word used against its glossary meaning gets called out
  at once: "the glossary says a land is X; you mean Y?"
- **Sharpen fuzzy words.** An overloaded word gets a proposed precise term, and the losers go
  under `_Avoid_`.
- **Test with scenarios.** Invent concrete edge cases (two players, the world's edge, a save
  from before the change) that force the boundary between two concepts.
- **Check the code.** When the owner says how something works, grep it. A contradiction is a
  question: "the code does X, you said Y. Which is right?"

## Writing as you go
- **Glossary**, the moment a term settles: `**Term**:` then one or two sentences on what it is,
  `_Avoid_:` for rejected words, and a code name only where the word is ambiguous. No rules or
  how-it-works; those belong in specs.
- **Decision record**, offered only when all three hold: hard to reverse, surprising without
  context, a real trade-off. One paragraph (context, decision, why); add "Considered options"
  only when a rejected option will be suggested again. Name it `<date>-<slug>.md`.
- Commit those files alone, plus a link from the spec they explain, and push.

## Done
The talk is done when no branch is left open and nothing is silently assumed. Sum up the
decisions in a few lines and wait for the owner to confirm. If a buildable idea came out of it,
offer crew-ticket; don't write the ticket here.
