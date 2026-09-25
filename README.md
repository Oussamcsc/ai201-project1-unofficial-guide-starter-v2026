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

Raw file: [`results/run_2026-09-25_1615_before.md`](results/run_2026-09-25_1615_before.md),
written by `run_eval.py::main`. Three runs of all five questions with caching
off, 15 model calls, 6,922 tokens. No code changed between the runs.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 2. Every answer names a source | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 4. Chunks keep the answer sentence whole, with its topic | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 5. Answer is correct and grounded in what it cites | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |

**Three of these five do not vary between runs, and that is a fact about the
criteria rather than a shortcut.** Criterion 3 is a comparison against a fixed
number. Criterion 1 is a fixed query against a fixed index — the same chunks
come back every time. Criterion 4 never touches a run at all; it is a property
of `chunker.py::split_documents` output. Only criteria 2 and 5 depend on
generation, and those are the two where the text below actually differs between
runs.

### Criterion 1 — a retrieved chunk contains the answer · 5/5

Produced by `scorer.py::retrieval_contains_answer` over `store.py::search`
(`python scorer.py`). Verbatim:

```
  Q1  PASS  expects 'three days'  (best distance 0.193)
        1. admin_parking_permits.txt#0                0.193  <-- has the answer
        2. dining_halden_hall.txt#1                   0.613
        3. advising_registration.txt#0                0.619
        4. transit_walking.txt#0                      0.626
  Q2  PASS  expects 'credit hours'  (best distance 0.205)
        1. admin_housing_lottery.txt#0                0.205  <-- has the answer
        2. advising_registration.txt#0                0.674  <-- has the answer
        3. course_stat_150_exams.txt#0                0.724
        4. housing_tamsin_court.txt#1                 0.736
  Q3  PASS  expects 'two weeks'  (best distance 0.370)
        1. advising_registration.txt#0                0.370  <-- has the answer
        2. health_center.txt#1                        0.563
        3. admin_library_holds.txt#0                  0.616
        4. orientation_what_matters.txt#0             0.625
  Q4  PASS  expects 'W'  (best distance 0.202)
        1. admin_add_drop_deadline.txt#0              0.202  <-- has the answer
        2. admin_withdrawal_deadline.txt#0            0.418  <-- has the answer
        3. admin_pass_fail_option.txt#0               0.505
        4. admin_transcript_requests.txt#0            0.537
  Q5  PASS  expects '20 to 25 minutes'  (best distance 0.173)
        1. dining_kestrel_commons_followup.txt#0      0.173  <-- has the answer
        2. dining_kestrel_commons_followup.txt#1      0.390
        3. dining_halden_hall_followup.txt#0          0.402
        4. dining_the_ridgeway_cafe_followup.txt#0    0.407

  -> 5 of 5 questions. Target: 4 of 5.
```

### Criterion 2 — every answer names a source · 5/5 in all three runs

Produced by `generate.py::answer_from_chunks` under `GROUNDING_INSTRUCTION`,
checked by `scorer.py::names_a_source`. The filename is inside the answer text
— app.py prints a `Sources retrieved:` line of its own, and counting that would
score the retriever rather than the answer. All 15 answers named a file, and
every file named was one that had really been retrieved. The model is
inconsistent about *how* it cites, which is worth seeing — three formats from
three questions in run 1:

```
Student permits for the west lots sell out in about three days. (Source: admin_parking_permits.txt)
```
```
Juniors and seniors are ordered by accumulated credit hours first, with ties broken randomly in the housing lottery.

Source: admin_housing_lottery.txt
```
```
If you drop a course after week two, it shows as a W on your transcript (admin_add_drop_deadline.txt).
```

Run 2 of question 2 wrapped the filename in backticks — `` `admin_housing_lottery.txt` `` — which is the one place the three runs visibly differ on this criterion. The criterion says *names* a source, not *formats it a fixed way*, so all three count.

### Criterion 3 — the gate stops out-of-corpus questions · 5/5

Produced by `run_eval.py::check_out_of_scope` at cutoff 0.70. Verbatim:

```
Out-of-scope questions (the gate should refuse these):
  refused  (best distance 0.825)  What is the capital of Mongolia?
  refused  (best distance 0.932)  How do I change the oil in a diesel engine?
  refused  (best distance 0.886)  Who won the 1994 World Cup?
  refused  (best distance 0.849)  What is the recommended dosage of ibuprofen for a headache?
  refused  (best distance 0.891)  How do I write a for loop in Rust?
  -> gate refused 5 of 5
```

### Criterion 4 — chunks keep the answer sentence whole, with its topic · 5/5

Produced by `scorer.py::chunk_check` on `chunker.py::split_documents` output.
It never goes through retrieval — the criterion exists to say something about
the chunks themselves. Verbatim:

```
  Q1  PASS  admin_parking_permits.txt (1 chunk(s))
        in admin_parking_permits.txt#0
  Q2  PASS  admin_housing_lottery.txt (1 chunk(s))
        in admin_housing_lottery.txt#0
  Q3  PASS  advising_registration.txt (1 chunk(s))
        in advising_registration.txt#0
  Q4  PASS  admin_add_drop_deadline.txt (1 chunk(s))
        in admin_add_drop_deadline.txt#0
  Q5  PASS  dining_kestrel_commons.txt (2 chunk(s))
        in dining_kestrel_commons.txt#0

  -> 5 of 5 posts pass. Target: 5 of 5.
```

### Criterion 5 — the answer is correct and grounded in what it cites · 5/5 in all three runs

Produced by `generate.py::answer_from_chunks`, scored by `scorer.py::judge` and
then read by hand for the half `judge` cannot decide (see that function's
docstring). Question 2 is the one that moves between runs, so all three of its
answers are here:

```
run 1: Juniors and seniors are ordered by accumulated credit hours first, with ties broken randomly in the housing lottery.
run 2: Juniors and seniors are ordered by accumulated credit hours first, with ties broken randomly in the housing lottery.
run 3: Juniors and seniors are ordered by accumulated credit hours first, with a random tie-break used only when necessary.
```

`admin_housing_lottery.txt` says *"juniors and seniors are ordered by
accumulated credit hours first, and only tie-break randomly."* Run 3's
rephrasing — "used only when necessary" — is the one I looked at hardest,
because it adds a word the document does not use. I counted it supported: "only
tie-break randomly" means the random step applies only to ties, which is what
"only when necessary" says. It is a paraphrase, not a new claim.

This is also the distinction the corpus exists to make. A model answering from
training data would say a housing lottery is random, because that is what the
word means. All three runs got it right and named the file.

## Verdicts

Against the targets in [`criteria.md`](criteria.md), written in unit 1 before
any of these results existed. Nothing below uses a target I set this unit.

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 | A retrieved chunk contains the answer | 4 of 5 | **MET** | 5/5, and the answer-bearing chunk is at rank 1 for all five questions, so there is no reading of the numbers where this is close. The caveat below is about how generously I measured it, not about the count. |
| 2 | Every answer names a source | 5 of 5 | **MET** | All 15 answers named a `.txt` file, and in every case the file named was one retrieval had actually returned — so none of them is a filename the model invented. This was the target most at risk of a single miss, because 5 of 5 allows none, and it held three times over. |
| 3 | The gate stops out-of-corpus questions | 4 of 5 | **MET** | 5/5, refused at 0.825–0.932 against a 0.70 cutoff. The closest of the five was 0.125 clear of the line. This is the least surprising MET on the list — unit 1 set the cutoff using these same five questions, so passing it now is partly a measure of that calibration rather than of the gate. |
| 4 | Chunks keep the answer sentence whole, with its topic | 5 of 5 | **MET** | 5/5. Four of the five posts stayed whole as single chunks, so the only real test was `dining_kestrel_commons.txt`, which splits into two — and the wait-time sentence survived intact in chunk 0 with the title attached. |
| 5 | The answer is correct and grounded in what it cites | 4 of 5 | **MET** | 15/15 across three runs. I read every answer rather than trusting `scorer.py::judge`, because `judge` cannot see an invented claim sitting next to a correct one. The one I weighed was run 3 of question 2, reasoning in the section above; I counted it supported. No answer in any run made a claim its cited document does not carry. |

**All five met, on the first test.** Milestone 3 has the honest reading of that.

### On revising a criterion: I'm not revising any, and here's why

The rule is that a criterion can be revised when it turned out to be
*unmeasurable* or measured the wrong thing — not when it was fine and I merely
cleared it. Two of mine have measurement looseness worth recording, and neither
rises to a revision:

- **Criterion 1's proxy is more generous than the criterion.**
  `scorer.py::retrieval_contains_answer` treats a chunk as containing the answer
  if it contains the `expects` phrase. For question 4 that phrase is `W`, and
  `admin_withdrawal_deadline.txt` — a document about *withdrawal*, which the
  corpus says is a different thing from dropping — also contains a standalone
  W. My scorer marks it as having the answer. It does not. The verdict is
  unaffected, because the genuinely correct chunk is at rank 1, but if the
  ranking ever flipped, criterion 1 would report a pass I hadn't earned. That's
  a flaw in my *measurement*, and the criterion as worded ("contains the
  answer") is the thing that's right.
- **Criterion 4 depends on strings I chose.** "The relevant topic identifier"
  left me to decide what the identifier was for each post, and I picked them in
  `scorer.py::ANSWER_SENTENCES` after seeing the corpus. A stricter or looser
  choice of identifier would move the result. I pinned the quoted sentences
  against the documents at import so they can't drift, but the topic strings are
  still a judgment I made once.

Recording both here rather than quietly revising: the point of leaving the
originals visible is that someone can see what I said before I knew the answer,
and neither of these is a case where I'd have written the criterion differently
for measurement reasons. Where I *would* write them differently is about height,
not measurability, and that belongs in *What I'd Do Differently*.

## Diagnoses

**I missed nothing. Five for five, three times over.** The brief says a system
that clears every criterion on the first try usually means the criteria were
safe rather than the system excellent, and having gone looking, that is what
happened here.

### The pattern, and it is one problem rather than five

All five of my test questions ask for a **single short fact from a single
short, single-topic admin post**: three days, credit hours, two weeks, a W, 20
to 25 minutes. Unit 1 already found this — *"My five test questions all target
short, single-topic admin posts, so the in-corpus group above is easier than
the corpus really is"* — and used fifteen extra questions to set the gate
because of it. What I didn't do in unit 1 was carry that insight into the
criteria. All five criteria are evaluated against those same five easy
questions, so **every criterion inherits the same blind spot**, and passing all
five is closer to one result than to five.

The clearest evidence is that the answer-bearing chunk comes back at **rank 1
for all five questions**, at distances of 0.173 to 0.370. Criterion 1 only asks
that it be somewhere in the top four. There is no question in my set where
retrieval has to work hard, so criterion 1 cannot fail and cannot tell me
anything.

### What the test cannot see: the retrieval tail

Criterion 1 asks whether *one* of the four retrieved chunks has the answer. It
says nothing about the other three, and those three go into the prompt too.
Measured across all five questions (`store.py::search`, top-k 4):

| Q | rank 1 | rank 2 | rank 3 | rank 4 |
|---|---|---|---|---|
| 1 | 0.193 | 0.613 | 0.619 | 0.626 |
| 2 | 0.205 | 0.674 | **0.724** | **0.736** |
| 3 | 0.370 | 0.563 | 0.616 | 0.625 |
| 4 | 0.202 | 0.418 | 0.505 | 0.537 |
| 5 | 0.173 | 0.390 | 0.402 | 0.407 |

**8 of the 20 chunks that reach a prompt are further away than 0.610** — the
hardest question unit 1 found the corpus genuinely answers. **Two of them are
past 0.70, the gate's own cutoff.**

That second number is not a matter of taste, it is the pipeline contradicting
itself. **Stage: retrieval.** **Mechanism:** `store.py::search` returns a fixed
count and `gate.py::check` only ever looks at `min(distance)`, so a chunk's
distance decides its fate differently depending on where it ranks. Ask a
question whose best chunk is 0.71 and the system refuses to answer at all,
calling that material too thin to reason from. Ask question 2, and
`housing_tamsin_court.txt#1` at **0.736** — further away than the chunk that
would have triggered a refusal — is placed in the prompt as context. Same
distance, opposite treatment, decided only by rank. Unit 1 flagged exactly this
and deferred it: *"The real fix is to filter the retrieved chunks by distance
before building the prompt, rather than passing a fixed count. That's a unit 2
change, noted here so it's on record."*

### The near miss criterion 1 scored as a pass

Question 5 asks about the wait at Kestrel Commons. The post I wrote the
question from is `dining_kestrel_commons.txt`, and **it does not appear in the
top four at all** — its two chunks rank 5th (0.408) and 7th (0.426). What ranks
1st and 2nd is `dining_kestrel_commons_followup.txt`, a different post that
happens to restate the same figure, and ranks 3 and 4 are **two other dining
halls entirely** — Halden Hall at 0.402 and the Ridgeway Cafe at 0.407.

So half the prompt for question 5 is about the wrong building, and the answer
is correct only because a corroborating post exists. **Stage: embedding.**
**Mechanism:** every dining followup post shares a near-identical shape —
"Re: <hall>", a wait time, a queue observation — so the embedding is dominated
by the *form* of a dining-hall post rather than by which hall it names. The
building name is one short token against two hundred characters of shared
phrasing. Criterion 4 confirms the chunking is not at fault: the Kestrel
sentence is intact in `dining_kestrel_commons.txt#0` with its title attached.
The chunk is fine; the ranking is what's wrong.

This one is real but I am not fixing it — see *What's Still Broken*.

### Were the targets set low? Yes. Which one I'd tighten, and to what

Criterion 1 is the one to tighten. "One of the top four has the answer" is a
bar my system clears without effort, and it is blind to the three chunks it
doesn't ask about.

> **The tightened version, for the next unit:** *Every chunk placed in the
> model's prompt is closer than the relevance cutoff the gate uses to refuse
> (0.70).*

Measured now, before any change: **18 of 20 chunks pass, so 18/20 is the
before-number.** It is a real bar rather than a comfortable one — it can fail,
it just failed twice, and it makes the system answer to the same standard in
both directions instead of applying 0.70 only to the best chunk.

This is written here as the tightening Milestone 3 asks for, **not** as a sixth
criterion and not as a replacement for criterion 1. The verdict table above
still judges criterion 1 at 4 of 5, which is what [`criteria.md`](criteria.md)
says, and it is still MET.

## The Improvement

**What I changed:** `gate.py::keep_relevant` — a new function that drops
retrieved chunks the gate would not have accepted as a best match.
`generate.py::build_prompt` calls it, so the chunks that reach the model are
the ones under the 0.70 cutoff rather than a fixed count of four.

Filtering inside `build_prompt` rather than at each call site means `app.py`,
`run_eval.py` and `serve.py` all get the change without being touched, and
`--show-prompt` keeps printing exactly what was sent. It cannot empty the
list: `gate.check` has already established that the best chunk is under the
threshold, so that chunk always survives.

**Why I picked it:** my diagnosis found the pipeline applying one number two
opposite ways — refusing a question whose best chunk is 0.71 as too thin to
reason from, while putting `housing_tamsin_court.txt#1` at **0.736** into
question 2's prompt as context — and this makes 0.70 mean the same thing in
both directions.

It is also the fix unit 1 wrote down and deferred: *"The real fix is to filter
the retrieved chunks by distance before building the prompt, rather than
passing a fixed count. That's a unit 2 change, noted here so it's on record."*

**One other commit touches config.py** — `REQUESTS_PER_MINUTE` from 30 to 12,
because the free tier allows 15/min and the first attempt at the after-run died
on a real 429 partway through. It paces calls and cannot change an answer. It
is committed on its own, separately from the improvement, so the one-change
rule stays checkable in the history.

### Run Log — After

Raw file: [`results/run_2026-09-25_1733_after.md`](results/run_2026-09-25_1733_after.md),
written by `run_eval.py::main`. Same command, same five questions, three runs,
caching off. 15 model calls, 6,450 tokens.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 2. Every answer names a source | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 4. Chunks keep the answer sentence whole, with its topic | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 5. Answer is correct and grounded in what it cites | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |

Side by side:

| | Before | After |
|---|---|---|
| Criteria 1–5 | 5/5 all three runs | 5/5 all three runs — **no change** |
| Chunks placed in prompts (5 questions) | 20 | 18 |
| Of those, under the 0.70 cutoff | 18 of 20 | **18 of 18** |
| Furthest chunk put in a prompt | 0.736 | 0.674 |
| Prompt characters, five questions | 6,963 | 6,373 (−8.5%) |
| Input tokens, 15 calls | 6,447 | 5,988 (−459) |
| `test.py` | 10 passed | 10 passed |

Only question 2 changed at all. `course_stat_150_exams.txt#0` (0.724) and
`housing_tamsin_court.txt#1` (0.736) stopped being handed to the model. The
other four questions had no chunk past the cutoff, so their prompts are byte
for byte what they were — which is the result I wanted, since a filter that
quietly rewrote prompts it had no reason to touch would be a worse change.

Question 2 after the change, all three runs, from
`generate.py::answer_from_chunks`:

```
run 1: Juniors and seniors in the housing lottery are ordered by accumulated credit hours first, with any ties broken randomly. (Source: admin_housing_lottery.txt)
run 2: Juniors and seniors in the housing lottery are ordered by accumulated credit hours first, with a random tie-break used only when necessary (admin_housing_lottery.txt).
run 3: Juniors and seniors are ordered by accumulated credit hours first, with ties broken randomly.

Source: admin_housing_lottery.txt
```

**One thing to read carefully in the raw file.** Its `Sources retrieved:` line
still lists all four documents for question 2, including the two that were
dropped. That is not the filter failing — `run_eval.py::main` records
`results` straight from `store.py::search`, before the prompt is built, so that
line reports what retrieval returned and not what the model saw. I left
`run_eval.py` alone rather than edit the harness to flatter my own change. The
evidence the filter was live is the token count: the change removes 590
characters from question 2's prompt, question 2 ran three times, and the after
run used **459 fewer input tokens** than the before run. That is the right size
for three prompts each ~150 tokens shorter, and nothing else changed.

**Did it help?**

**It helped the system, and it did not move a single criterion — and the second
half is the more useful finding.**

What it demonstrably fixed: every chunk that reaches the model is now one the
gate would accept, 18 of 18 against 18 of 20 before. The worst chunk in any
prompt went from 0.736 to 0.674. The pipeline no longer contradicts itself.

What it did not do: change any of my five criteria, which sat at 5/5 before and
sit at 5/5 after. **They could not have moved.** They were already at ceiling,
so the only thing this change could have done to them is break one, and it
broke none — all 15 answers still correct, still grounded, still citing a
document that was really retrieved, `test.py` still 10 passed.

I could present "no regression" as a win and stop. The honest version is that
**my criteria cannot see this improvement at all.** A change that removes two
irrelevant documents from a prompt, shrinks it by 8.5%, and makes the system
apply one standard consistently registers as exactly zero across all five
things I said "working" meant. That is a fact about criterion 1 — "one of the
top four has the answer" is indifferent to what the other three are — and it is
why the tightened version in *Diagnoses* is written at chunk granularity
instead. Measured against that bar, the change is 18/20 → 18/18.

Being precise about what I have and haven't shown: I have **not** shown this
makes answers better, because I had no failing answer to fix. On a harder
question set — one where a 0.736 chunk about Tamsin Court sits next to a real
answer and the model has to choose — I would expect it to matter, and I have no
evidence of that here. What I have shown is that it costs nothing and removes a
real inconsistency.

## What's Still Broken

No criterion is missed, before or after. So this section is about the things
the criteria never asked about, which is where everything broken in this system
actually is.

**1. Question 5's own source post never reaches the model.** Diagnosed above as
an embedding problem: `dining_kestrel_commons.txt` ranks 5th and 7th, below
`dining_halden_hall_followup.txt` and `dining_the_ridgeway_cafe_followup.txt`,
because every dining followup shares the same shape — "Re: <hall>", a wait
time, a queue remark — and the hall's name is one short token against two
hundred characters of identical phrasing. The answer is right only because a
corroborating post happens to rank first. Remove that one file and I believe
question 5 starts answering about the wrong dining hall.

What I'd do: hybrid search. BM25 scores the literal token "Kestrel", which is
exactly what the embedder is drowning out, and the brief names this as the case
where keyword search earns its place. `rank-bm25` is already in
`requirements.txt`.

Why I stopped: the one-change rule, and I picked the other fix deliberately.
Hybrid search changes the score scale, and every number in this system — the
0.70 cutoff, `gate.check`, and now `keep_relevant` — is calibrated against
cosine distance from unit 1. Recalibrating the gate to suit a new scale would
have been a second change dressed up as part of the first, and I'd have been
unable to say which of the two moved anything. That's the trade I made
knowingly, not something I ran out of time for.

**2. I have not shown the improvement improves an answer.** It removes two
irrelevant chunks and costs nothing, and that is the whole of what I measured.
Whether a distant chunk actually pulls an answer off course is untested,
because no question in my set is hard enough to put it to the test.

What I'd do: write questions where two documents genuinely compete — the corpus
has the pairs for it, `admin_add_drop_deadline.txt` against
`admin_withdrawal_deadline.txt`, which both mention a W and week six, and the
seven dining followups against their originals. Then a distant chunk has
something to spoil.

Why I stopped: new questions are a unit 1 artefact, and changing them now would
mean my before and after run logs were measuring different things. The right
place for this is the start of the next unit, not the end of this one.

**3. `scorer.py::judge` can be fooled and I know how.** It checks that the
answer carries the expected fact and cites a real document. An answer that
carries the right fact *and an invented one beside it* passes. This unit I
covered that by reading all 30 answers myself, which is why criterion 5's
verdict is mine rather than the script's. That does not scale, and a future
unit with more questions would need the reading replaced with something
better — most likely checking each claim against the cited chunk rather than
checking the answer as a whole.

**4. Criterion 1's `W` proxy matches the wrong document.** Written up under
*Verdicts*. It doesn't affect any verdict here because the correct chunk ranks
first, but it is a measurement that would report a pass I hadn't earned if the
ranking ever flipped. A fix would score the chunk that contains the fact *in
the right context* rather than the fact alone — which is roughly what criterion
4 already does for chunks, so the machinery exists.

## What I'd Do Differently

**Criterion 1, and it's not close.** "For at least 4 of my 5 test questions,
the retrieved chunks include one that contains the answer" asks whether the
answer is *somewhere* in the top four. My system puts it at **rank 1 for all
five questions, at 0.173–0.370**. The criterion cannot fail, and a criterion
that cannot fail cannot teach me anything — it scored 5/5 before my improvement
and 5/5 after, while the thing I actually fixed lived entirely in the three
chunks it never looks at.

I'd write it at chunk granularity instead: *every chunk placed in the model's
prompt is closer than the cutoff the gate uses to refuse.* That version was
failing before this unit's change (18 of 20) and passing after (18 of 18),
which is what a useful criterion looks like — one whose number moves when the
system does.

**The deeper mistake was in the questions, not the criteria.** All five ask for
one short fact from one short single-topic admin post. Unit 1 *found* this —
that's why the gate was calibrated on fifteen extra questions rather than these
five — and then wrote five criteria that all rest on the same five easy
questions anyway. Every criterion inherited the same blind spot, so five
criteria gave me roughly one result five times. Next time I'd write the
criteria against the hardest questions the corpus can support, not the ones I
was confident about.

**Criterion 3 I'd measure on different questions.** Mongolia, diesel engines
and the 1994 World Cup are from another world, so refusing them is easy, and
unit 1 set the 0.70 cutoff using these same five — passing it now is partly a
measure of that calibration rather than of the gate. Unit 1 already found the
questions that would make it a real test: campus-flavoured ones the documents
don't cover, which land at 0.387–0.724, *inside* the in-corpus range, and which
`GROUNDING_INSTRUCTION` catches instead of the gate. Criterion 3 should have
been written against those, where it would have been genuinely at risk.

**Criterion 2 I'd keep exactly as it is.** 5 of 5 allows no misses, it's
unambiguous, and it held 30 times out of 30 across both run logs. Not every
criterion needs to be harder — this one is cheap to check and would catch a
real regression the day the grounding prompt drifts.

## How I Used AI — unit 2

Unit 1's two entries are above and still stand. Three things this unit.

**1. I used it to find the pattern, because everything passed and I needed
something to diagnose.**

Five criteria, 5/5, three runs. There was no failure to trace, which is the
least useful outcome the unit can produce. So I had it measure what the
criteria *don't* look at — every retrieved chunk at every rank, not just the
one criterion 1 asks about. That produced the two findings the rest of the
write-up rests on: 8 of 20 chunks in prompts past 0.610, two past the gate's
own 0.70, and question 5's source post sitting at rank 5 below two unrelated
dining halls.

Neither of those is visible from the run log `run_eval.py` produces. Both were
there the whole time.

**2. I made it argue against my own verdicts, and kept the verdict anyway.**

Milestone 2 suggests asking for the opposite case. The one worth testing was
criterion 5, run 3 of question 2, where the answer says *"a random tie-break
used only when necessary"* and `admin_housing_lottery.txt` says *"only
tie-break randomly."* The case against me: "necessary" implies discretion the
document never grants — the document makes the random step apply to ties as a
rule, while "when necessary" could be read as the office using randomness
sparingly when it feels the need. Under criterion 5 an unsupported claim fails
the question, so that would be 4/5 rather than 5/5.

I kept MET. A tie-break is by definition only needed when there is a tie, so
"only when necessary" and "only tie-break randomly" pick out the same cases.
The criterion would still have been MET at 4/5, so nothing hung on it — but it
is the one place in the run where I could have talked myself into either
answer, and it is recorded rather than smoothed over.

**3. Where I overruled it.**

It offered to revise criterion 1, pointing at the genuine measurement flaw in
my `W` proxy — `admin_withdrawal_deadline.txt` also contains a standalone W, so
the scorer counts a document about withdrawal as containing the answer to a
question about dropping. That flaw is real and it's written up under
*Verdicts*. But the revision rule is for criteria that couldn't be measured,
and mine measured fine; what's wrong with criterion 1 is that it is too easy,
and the brief is explicit that a criterion you merely cleared doesn't get
rewritten. Revising it would have been taking credit for a rule I'd have been
bending. It stays as written, the flaw is recorded, and the tightening lives in
*What I'd Do Differently* where it can't be confused for a verdict.

I also turned down a second improvement. Hybrid search is the obvious fix for
the question 5 finding and it was on the table — but it changes the score scale
that the 0.70 cutoff, `gate.check` and `keep_relevant` are all calibrated
against, so it would have meant recalibrating the gate too, and I'd have had
two changes and no way to say which one moved anything. The reasoning is under
*What's Still Broken*.
