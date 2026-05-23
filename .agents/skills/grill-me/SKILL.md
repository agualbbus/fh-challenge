---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

# Grill Me

## Core instructions

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Agent behavior

1. **Start from context** — Read any plan, spec, or doc the user points at (or the active topic) before the first question.
2. **Order by dependencies** — Ask about decisions that block other branches first; do not jump to leaf details until parent choices are settled.
3. **One question per turn** — Wait for the user's answer (or acceptance of your recommendation) before the next question.
4. **Recommend, then listen** — End each turn with one clear question and your recommended answer with brief rationale.
5. **Codebase first** — If the answer is knowable from the repo (stack, patterns, existing APIs, constraints), investigate and state what you found instead of asking.
6. **Track progress** — Keep a mental map of resolved vs open branches; when a branch is settled, move to the next unresolved dependency.
7. **Stop when aligned** — Summarize shared understanding (decisions + rationale) when the tree is resolved or the user says they're done.
