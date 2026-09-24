# The Unofficial Guide

**Oussama Abouyahia** — corpus: `campus_life`

A retrieval-augmented question-answering system over student-written campus
advice, built for AI-201 Project 1. How the starter works and every command
you'll need is in `RUNNING.md`.

---

# Unit 1

## What This Does

This is a question-answering system over `campus_life` — 88 short posts, about
28,000 characters in total, in which students tell each other how the place
actually works: which dining hall has a twenty-minute queue at lunch, what the
housing lottery really sorts on, which dorm has radiators you can't turn down.
It is the knowledge that never makes it into the course catalogue.

You ask a plain question and it answers from those documents and nothing else,
naming the file it used. It answers factual questions with a specific right
answer — *"How quickly do west-lot parking permits sell out?"*, *"What appears
on my transcript if I drop a course after week two?"*, *"How are juniors and
seniors prioritized in the housing lottery?"* — rather than matters of taste
like which dining hall is best, which these documents disagree about anyway.

Two separate mechanisms stop it inventing things. A relevance gate measures how
close the best retrieved chunk is before the model is called at all, and
refuses outright above 0.70. Anything that gets past the gate is answered under
an instruction to use only the supplied documents and to say so when they don't
cover the question. The first catches questions from another world; the second
catches the near misses — campus-sounding questions these particular documents
happen not to cover, which measure *inside* the answerable range and which no
cutoff could separate. Both layers are measured in the sections below.

Run it with `python app.py index` then `python app.py ask "your question"`.
Every command is in `RUNNING.md`.

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

**Question:** How are juniors and seniors prioritized in the housing lottery?

**Answer:** (verbatim from `python app.py ask "..."`)

```
  (best distance 0.205, cutoff 0.7)

Juniors and seniors are ordered by accumulated credit hours first, with ties
broken randomly in the housing lottery.

Source: admin_housing_lottery.txt

Sources retrieved: admin_housing_lottery.txt, advising_registration.txt,
course_stat_150_exams.txt, housing_tamsin_court.txt

1 model calls this session, 469 tokens (436 in, 33 out)
```

This is the distinction the corpus exists to make. A model answering from
training data would say a housing lottery is random — that's what the word
means. `admin_housing_lottery.txt` says rising sophomores are random but
juniors and seniors are ordered by credit hours and only tie-break randomly.
The answer gets it right and names the file.

**My relevance cutoff: 0.70** (`config.THRESHOLD`)

**Top-k: 4** (`config.TOP_K`)

### The two groups — all ten rows

| Question | In corpus? | Best distance |
|---|---|---|
| How quickly do student parking permits for the west lots sell out? | yes | 0.193 |
| How are juniors and seniors prioritized in the housing lottery? | yes | 0.205 |
| How far in advance should students book an adviser appointment before registration? | yes | 0.370 |
| What appears on your transcript if you drop a course after week two but before the dropping deadline? | yes | 0.202 |
| How long is the wait at Kestrel Commons between 12:15 and 1:00? | yes | 0.173 |
| What is the capital of Mongolia? | no | 0.825 |
| How do I change the oil in a diesel engine? | no | 0.932 |
| Who won the 1994 World Cup? | no | 0.886 |
| What is the recommended dosage of ibuprofen for a headache? | no | 0.849 |
| How do I write a for loop in Rust? | no | 0.891 |

Two groups, clearly separated: **0.173–0.370** and **0.825–0.932**. The
midpoint of that gap is 0.597, which is almost exactly the 0.6 the starter
ships. On this table alone, every cutoff from 0.45 to 0.75 scores identically
— 0 wrong refusals, 0 wrong passes. **The table cannot tell me what the number
should be**, and I nearly stopped here and kept 0.6 on the strength of it.

### Why I didn't keep 0.6

My five test questions all target short, single-topic admin posts, so the
in-corpus group above is easier than the corpus really is. I wrote fifteen more
questions the documents genuinely answer and measured those too:

| Question the corpus answers | Best distance |
|---|---|
| How much does laundry cost in the Old Brewhouse? | 0.170 |
| What does an official transcript cost? | 0.209 |
| Can I change my meal plan after the term starts? | 0.281 |
| How do group study rooms get booked? | 0.290 |
| How many hours a week outside class does CS 210 take? | 0.300 |
| Is Innisfree Hall noisy? | 0.301 |
| What is the pass/fail deadline? | 0.339 |
| How long does the shuttle take? | 0.369 |
| When does the salad bar go downhill? | 0.442 |
| What is the printing quota? | 0.445 |
| Are CS 210 midterms curved? | 0.424 |
| What happens if I miss the parking permit window? | 0.502 |
| Which building has heating that runs hot and cannot be adjusted? | 0.591 |
| What should I bring for winter? | 0.592 |
| **Do I need an adviser signature to withdraw?** | **0.610** |

That last one is the decisive measurement. `admin_withdrawal_deadline.txt`
says *"Withdrawal runs to week ten, **requires an adviser signature**, and puts
a W on the transcript."* The question is answered almost word for word, and it
retrieves at 0.610. **At the starter's 0.6, my system refuses it.**

So the honest in-corpus range is **0.170 – 0.610**, not 0.173 – 0.370. Against
out-of-scope at 0.825 – 0.932, the real gap is **0.610 to 0.825**, and I put
the cutoff at its midpoint:

| | |
|---|---|
| Highest distance on a question the corpus answers | 0.610 |
| **My cutoff** | **0.70** |
| Lowest distance on a question it doesn't | 0.825 |

That leaves 0.090 of headroom above the hardest answerable question and 0.125
below the easiest out-of-scope one. Verified after the change: **all 5 test
questions still pass the gate, and all 5 `OUT_OF_SCOPE` questions are still
refused, 5/5.**

### What 0.70 gets wrong, and why no number fixes it

The `OUT_OF_SCOPE` questions are from "a different world entirely" — Mongolia,
diesel engines, Rust. That's what makes the gap look clean. So I also tried
eight questions that *sound* like campus questions but that my documents don't
cover:

| Campus-flavoured, not in the corpus | Best distance | What it retrieved |
|---|---|---|
| What time does the campus bookstore close on Sunday? | 0.387 | `study_library_hours.txt` |
| How do I appeal a parking ticket I got on campus? | 0.568 | `admin_grade_appeals.txt` |
| How do I apply for a single room as a first-year? | 0.589 | `advising_registration.txt` |
| Is there a shuttle to the airport during break? | 0.591 | `transit_shuttle.txt` |
| Where do I get a student ID card replaced? | 0.605 | `transit_shuttle.txt` |
| What is tuition for out-of-state students? | 0.618 | `admin_printing_quota.txt` |
| What are the rules for keeping a pet in the dorms? | 0.671 | `housing_innisfree_hall.txt` |
| How do I join the varsity swimming team? | 0.724 | `orientation_what_matters.txt` |

These land at **0.387–0.724 — inside my in-corpus range**. There is no cutoff
that refuses these and still answers the withdrawal question at 0.610. The two
groups genuinely overlap, so **the gate cannot solve this**. Lowering the
cutoff to catch them would refuse real questions, which is the more damaging
error of the two.

### The grounding instruction — read, tested, kept

That overlap is exactly what `GROUNDING_INSTRUCTION` in
[generate.py:276](generate.py#L276) is the second layer for, so I tested it
against the questions the gate lets through rather than assuming:

```
$ python app.py ask "What time does the campus bookstore close on Sunday?"
  (best distance 0.387, cutoff 0.7)
I don't have enough information to answer your question, as the provided
documents do not mention the campus bookstore.
```

```
$ python app.py ask "What are the rules for keeping a pet in the dorms?"
  (best distance 0.671, cutoff 0.7)
I don't have enough information to answer your question.
```

And the harder case — a question whose *topic* is in the corpus but whose
*fact* is not. `admin_parking_permits.txt` covers west-lot permits in detail
and never states a price:

```
$ python app.py ask "How much does a west lot parking permit cost?"
  (best distance 0.363, cutoff 0.7)
I do not have enough information to answer how much a west lot parking permit
costs.

Source: admin_parking_permits.txt
```

That is the case where a model invents "$150 per semester" and sounds right.
It didn't. **I left `GROUNDING_INSTRUCTION` unchanged** — not because I skipped
the step, but because I tried three ways to make answers drift past the sources
and couldn't. Tightening a prompt that is already holding would be changing
something I have no evidence is broken.

### Why top-k went from 5 to 4

The answer-bearing chunk comes back at **rank 1 for all five test questions**,
so k isn't doing retrieval work — every value from 3 to 8 scores 5/5 on
criterion 1. What k actually controls is how much loosely-related material
rides into the prompt. At k=5 the fifth chunk sat at 0.632, 0.747, 0.636, 0.576
and 0.408 — three of those five are further away than 0.610, the hardest
question my corpus genuinely answers. Material that distant is not context, it
is noise, and k=4 drops it at zero cost to criterion 1.

The tail is still not clean at k=4 — Q2's fourth chunk is `housing_tamsin_court.txt`
at 0.736, which has nothing to do with the lottery. The real fix is to filter
the retrieved chunks by distance before building the prompt, rather than
passing a fixed count. That's a unit 2 change, noted here so it's on record.

## How I Used AI

**1. I made it prove the chunking decision instead of taking its design.**

I asked Claude to help with Milestone 3. It came back with a strategy it called
title-anchored paragraph packing and a question about what size to use. I
didn't accept the premise: if no document in `campus_life` reaches the
starter's 800-character window, nothing ever splits, so one post already *is*
one chunk — why isn't that the right answer? I asked what I was missing.

It couldn't settle that from argument, so it built five different indexes as
Chroma variants and measured them against my five questions. The answer was
that **I was right and the reasoning was wrong**: no strategy beat any other on
my five questions, because all five target short single-topic admin posts. But
probes aimed at the long `housing_*` posts, which none of my questions touch,
showed whole-post chunking retrieving the Old Brewhouse heating question at
0.687 — above my cutoff, refused.

What I changed: it told me the strategy would split 16 documents and leave 72
whole. That was wrong. Sweeping the parameter showed it splitting 59 of 88 at
the size it had proposed. The sweep is why `CHUNK_SIZE` is 300, which splits
46 and leaves 42, and not the 260 it originally suggested.

**2. I didn't let it stop at the table the assignment asked for.**

For Milestone 4 I asked for the ten distances. They came back exactly as the
brief predicts — 0.173–0.370 in corpus, 0.825–0.932 out, midpoint 0.597 — which
points straight at keeping the starter's 0.6. Every cutoff between 0.45 and
0.75 scores identically on those ten rows, so the table I was told to build
cannot actually decide the number, and I'd have written down 0.6 and called it
measured.

Fifteen further questions the corpus genuinely answers reach 0.610 — *"Do I
need an adviser signature to withdraw?"*, answered almost word for word in
`admin_withdrawal_deadline.txt`. At 0.6 my own system refuses it. That's what
moved the cutoff to 0.70.

I also stopped taking stated figures on trust. The brief says the starter
produces a 2-character chunk on `advice_threads`; measured, it's 28 characters
(`re than breadth across five.`). This README says 28, because that's what I
can reproduce.

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
