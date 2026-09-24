# The Unofficial Guide

<!-- Replace this line with your name and which corpus you picked. -->

> **This file is your submission.** Fill it in as you go — most sections get
> written during the milestone that produces them, not at the end.
>
> How the starter works, and every command you'll need, is in `RUNNING.md`.
> Leave that file alone.
>
> **Paste everything as text.** No screenshots, no video. A typed table gets
> full credit; a picture of the same table gets none.
>
> Delete these instruction blocks as you replace them. The `<!-- -->` comments
> are notes to you and don't show up when the page renders — you can leave them
> or remove them.

---

# Unit 1

## What This Does

<!-- Three or four sentences. Which corpus you picked, and the kinds of
     questions your system answers. Write it for someone who has never seen
     this repo.

     Milestone 5. -->

## Chunking Strategy

**Chunk size:** 300 characters, title included — a *soft* target
**Overlap:** 100 characters, carried as whole trailing sentences

Function: `chunker.py::split_documents`. I call the strategy **title-anchored
paragraph packing**.

### What I noticed in the documents

`campus_life` is 88 posts totalling 27,908 characters — 178 to 549 characters
each, ~317 on average. Three things decided the design:

- **Nothing reaches 800.** The starter's `fallback_split` takes `text[0:800]`,
  finds the whole document, and stops. It returns 88 documents as 88 chunks. It
  is not chunking; it is doing nothing.
- **Every single post opens with a bare title line** — `On the parking
  permits`, `Kestrel Commons`, `CS 210 Data Structures`. All 88. The longest is
  47 characters. That line is where the *topic* lives.
- **The corpus is 271 blank-line-separated blocks in total** (counting those
  title lines), median 93 characters; the body blocks alone run to a median of
  112. Most posts hold two or three distinct thoughts separated by a blank line.

### Why not just leave it at one post per chunk

That was my first instinct, and it's half right. But "800 never fires" is a
fact about the number 800 versus my document lengths — it says nothing about
whether 317 characters is a good chunk size. Nobody picked 800 for these
documents. So I measured instead of assuming.

A chunk becomes exactly one vector: an average of everything in it.
`housing_old_brewhouse.txt` is 549 characters covering the building's history,
what's good about it, the heating, laundry prices, and the noise. Ask about any
one of those and the vector is only ever *moderately* close, because four
fifths of it is about something else.

That is not hypothetical. Here is the same question against both:

| Question | Whole post | Title-anchored, 300 |
|---|---|---|
| "Which building has heating that runs hot and can't be adjusted?" | **0.687** | **0.586** |

My relevance cutoff is 0.6. Whole-post chunking makes the system **refuse a
question the corpus answers in plain English**. Splitting the post fixes it.

### Why not split on every blank line

I tried that too, and it's measurably worse:

| Strategy | Chunks | Avg | Shortest | Criterion 4 | Worst in-corpus | Best out-of-scope | Gap |
|---|---|---|---|---|---|---|---|
| Whole post (`fallback_split`) | 88 | 317 | 178 | 5/5 | 0.370 | 0.825 | +0.455 |
| Split on every blank line | 271 | 101 | **10** | **3/5** | 0.387 | **0.780** | **+0.393** |
| **Title-anchored, 300** | **136** | **236** | **118** | **5/5** | 0.370 | 0.825 | +0.455 |

Splitting on blank lines orphans all 88 title lines into chunks that say
`Kestrel Commons` and nothing else, and it drops my own criterion 4 to 3/5.
It also *narrows* the gap — out-of-scope questions get closer (0.780 vs 0.825),
because tiny fragments match anything a little.

### How I landed on 300

I swept the target and watched the Old Brewhouse heating question, which is the
one that sits near my cutoff:

| Target | Chunks | Posts left whole | Posts split | Heating distance |
|---|---|---|---|---|
| 260 | 149 | 29 | 59 | 0.595 ✅ |
| **300** | **136** | **42** | **46** | **0.586 ✅** |
| 340 | 121 | 55 | 33 | 0.688 ❌ |
| 400 | 101 | 75 | 13 | 0.633 ❌ |
| 460 | 91 | 85 | 3 | 0.633 ❌ |
| 560 | 88 | 88 | 0 | 0.687 ❌ (= the starter) |

Only 260 and 300 bring it under the 0.6 gate. 300 wins because it gets the
lower distance *and* leaves 13 more posts intact.

**I changed my mind partway through, twice.** I started out arguing one post
should stay one chunk, and the five questions I wrote in Milestone 2 back that
up — they all target short, single-topic admin posts where splitting changes
nothing. What I'd missed is that none of my five questions go near the long
`housing_*` and `course_*` posts, which is exactly where whole-post chunking
breaks. Then I picked 260 before sweeping properly and found 300 strictly
better.

### The four rules, and what each one is for

| Rule | The failure it prevents |
|---|---|
| Title line comes off and is prepended to *every* chunk from that document | Kestrel's second paragraph reading "Hours are 7:00am to 9:00pm" — hours for *what?* Also my criterion 4. |
| Chunks are packed from whole paragraphs, never cut mid-sentence | `"Professor Smith's exams come from the"` |
| `CHUNK_SIZE` is a soft target — a long paragraph is never halved | Answer sentences landing across two chunks |
| Overlap carries whole *sentences* backwards, not a character window | The overlap itself being a fragment |

Measured result on 136 chunks: **shortest chunk 118 characters, zero chunks
under 100, criterion 4 passes 5/5.** The starter's chunker gives no such
guarantee — run it over `advice_threads` and its shortest chunk is 28
characters reading `re than breadth across five.`, a sentence cut in half
mid-word.

**On the overlap:** 100 characters changes no distance I could measure
(I tested 0, 60, 100 and 140 — identical gaps). I kept it because it raises the
shortest chunk from 90 to 118 characters and insures against an answer sentence
landing on a chunk boundary, at a cost of about 12% duplicated text. Being
honest: on this corpus the overlap is insurance, not an improvement.

## Sample Chunks

All five produced by `chunker.py::split_documents`, printed with
`python app.py chunks --from-doc <file>`.

**Chunk 1** — source: `dining_kestrel_commons.txt#0` — produced by: `chunker.py::split_documents`

```
Kestrel Commons

I'm a junior and I've done this twice now. Wait times: 20 to 25 minutes between 12:15 and 1:00, under 5 minutes before 11:45. The thing worth going for is the stir-fry station, made to order. The thing to know is that the salad bar wilts after 1:30.
```

*A post that split. This half holds my test question 5 and its `expects`
phrase, with `Kestrel Commons` attached so the number means something.*

**Chunk 2** — source: `dining_kestrel_commons.txt#1` — produced by: `chunker.py::split_documents`

```
Kestrel Commons

The thing to know is that the salad bar wilts after 1:30.

Hours are 7:00am to 9:00pm weekdays, 9:00am to 8:00pm weekends. Costs one meal swipe, or $12.50 cash.
```

*The other half — and the clearest picture of both mechanisms at once. The
title is re-attached, and the salad-bar sentence is the 100-character overlap
carried forward whole from chunk 1. Without the title this chunk would be
hours and a price belonging to nothing.*

**Chunk 3** — source: `housing_old_brewhouse.txt#1` — produced by: `chunker.py::split_documents`

```
Old Brewhouse — what it's actually like

The good: the most characterful building on campus and people get attached to it.

The bad: the heating is uneven — some rooms run hot all winter and can't be adjusted.
```

*The chunk that justifies the whole strategy. In the 549-character whole-post
version this sentence sat alongside the building's history, laundry prices and
noise, and the heating question retrieved at 0.687 — above my cutoff, refused.
On its own it retrieves at 0.586 and gets answered.*

**Chunk 4** — source: `admin_parking_permits.txt#0` — produced by: `chunker.py::split_documents`

```
On the parking permits

Student permits for the west lots go on sale in August and sell out in about three days. The east lot never sells out because it's a 12-minute walk. There is no waitlist — people who miss the window park on Verrill Street and walk in, which is legal but unmarked and confuses everyone.
```

*One of the 42 posts left whole. It is a single thought at 312 characters, so
the rule leaves it alone — the same output `fallback_split` gave, but now as a
decision rather than an accident of the number 800.*

**Chunk 5** — source: `admin_add_drop_deadline.txt#0` — produced by: `chunker.py::split_documents`

```
On the add/drop deadline

You can add a course through the end of the second week. Dropping is a longer window — through the end of week six — but a drop after week two shows as a W on your transcript. Nothing anywhere on the registrar's site says this plainly, and students find out from each other.
```

*Also left whole, and deliberately so. This answers my test question 4, and it
competes with `admin_withdrawal_deadline.txt`, which also mentions a W, week
six and week ten. Splitting the condition ("after week two") away from the
consequence ("shows as a W") would make the two documents indistinguishable to
the embedder. Keeping the sentence intact is what keeps them apart.*

## Sample Answer

<!-- One complete question and answer, pasted as text, with the source line
     visible. Milestone 4. -->

**Question:**

**Answer:**

```
```

**My relevance cutoff:**

<!-- The number you set in config.py, and how you got there.

     You ran five questions your corpus covers and the five in OUT_OF_SCOPE
     that it clearly doesn't, and wrote down the best distance for each. What
     did those two groups look like? Where was the gap? Put the actual numbers
     here — the table below wants all ten rows.

     Milestone 4. -->

| Question | In corpus? | Best distance |
|---|---|---|
|  |  |  |

## How I Used AI

<!-- Two specific moments. For each: what you asked for, what came back, and
     what you changed about it.

     "I asked Claude to write the chunking function from my notes. It ignored
     the overlap, so I added that myself" is the level of detail we're after.
     "I used AI to help me code" is not.

     Milestone 5. -->

**1.**

**2.**

<!-- ── Stretch features ─────────────────────────────────────────────────────
     Doing one? Say so here BEFORE you start. A feature this README never
     claims earns nothing.
     ───────────────────────────────────────────────────────────────────────── -->

---

# Unit 2

<!-- These sections get ADDED to what's already above. Don't delete or rewrite
     unit 1 — the point is that someone can see what you said before you knew
     how it went. -->

## Run Log — Before

<!-- Your five criteria, three runs each. `python run_eval.py --label before`
     runs the questions, puts the OUT_OF_SCOPE ones through the gate, and
     writes it all into results/ for you. Targets come from criteria.md; the
     verdict column is your call.

     Criterion 3 is measured in one deterministic pass rather than three, so
     the same number goes in all three run columns. That's correct, not lazy.

     Milestone 1. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 |  |  |  |  |
| 2. Every answer names a source | 5 of 5 |  |  |  |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 |  |  |  |  |
| 4. | | | | | |
| 5. | | | | | |

<!-- Underneath, paste the REAL output for each criterion from one of your
     runs — the actual text your system produced, not a description of it.
     Name the file and function that produced it. -->

## Verdicts

<!-- MET or MISSED for each of the five, against the target you wrote last
     unit — not a new one. Plus a sentence on how you decided. That sentence
     matters most where it was close.

     If your target said 4 of 5 and your runs came out 4, 3, 4, that's a MISS.
     The target has to hold, not show up occasionally.

     Milestone 2. -->

| # | Criterion | Verdict | How I decided |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |
| 4 |  |  |  |
| 5 |  |  |  |

## Diagnoses

<!-- For each miss: which stage caused it, and how. The stage alone isn't
     enough — you need the mechanism.

     Not a diagnosis: "Question 3 didn't work."
     A diagnosis:     "Question 3 asks about laundry costs. The answer is in
                       one sentence that got split across two chunks, so
                       neither chunk on its own contains it."

     The five stages: loading → chunking → embedding → retrieval → generation.

     Look for a pattern. If three misses all ask about numbers, that's one
     problem, not three.

     Missed nothing? Say so, then say honestly whether your targets were set
     low, and which one you'd tighten and to what.

     Milestone 3. -->

## The Improvement

**What I changed:**

**Why I picked it:**

<!-- Connect it to a specific diagnosis above in one sentence. If you can't,
     you picked a fix because it sounded impressive. -->

### Run Log — After

<!-- Same format, same five criteria, three runs each.
     `python run_eval.py --label after` -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 |  |  |  |  |
| 2. Every answer names a source | 5 of 5 |  |  |  |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 |  |  |  |  |
| 4. | | | | | |
| 5. | | | | | |

**Did it help?**

<!-- Say plainly whether it did, and how you know. If it made things worse,
     say that — a change that backfired, honestly reported, earns full credit
     and is more interesting than one that worked. What matters is that you can
     tell.

     Milestone 4. -->

## What's Still Broken

<!-- For each criterion still missed after your fix: what you'd do about it,
     and why you stopped where you did.

     "I ran out of time" is fine if it's true. Pretending nothing is left is
     not.

     Milestone 5. -->

## What I'd Do Differently

<!-- Knowing what you know now — which of your five criteria would you write
     differently, and why?

     Milestone 5. -->
