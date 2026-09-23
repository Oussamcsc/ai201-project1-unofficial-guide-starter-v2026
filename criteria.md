# Acceptance criteria — The Unofficial Guide

Five criteria that say what "working" means for this system, written in unit 1
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"Retrieval works"* is an opinion. *"For at
least 4 of my 5 test questions, the top results include a chunk containing the
answer"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter or looser one. A reason that says something about your corpus or your
pipeline earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

---

## 1. Retrieved chunks contain the answer

For at least 4 of my 5 test questions, the retrieved chunks include one that
contains the answer.

**Why this target:**
The posts are short, and each selected question has an explicit answer in the documents. However, posts about related topics—such as registration and housing both using credit hours—could compete in retrieval. Four successful retrievals allows one miss while requiring useful evidence for most questions.

---

## 2. Every answer names a source

Every answer the system produces names at least one source document.

**Why this target:**
The system supplies document filenames with the retrieved material, so source attribution should be achievable for every generated answer. Allowing an uncited answer would leave the reader unable to check its evidence. Gate refusals are assessed separately under criterion 3 and do not need a source citation.

---

## 3. The relevance gate stops out-of-corpus questions

When I ask a question my documents clearly don't cover, the relevance gate
stops it and the system returns "I don't have enough information about that" —
in at least 4 of 5 tries.



**Why this target:**
The five questions in OUT_OF_SCOPE concern subjects outside the campus documents. Most should therefore be rejected before generation. Some share vocabulary with campus topics, such as programming and courses, so semantic similarity may allow an irrelevant question through. Four of five requires consistent refusal without assuming perfect separation.

The cutoff has not yet been calibrated. Actual distances and the chosen cutoff will be recorded in the README during Milestone 4.
---

## 4. Something about your chunks

For each of the five source posts used to write my test questions, at least one produced chunk must contain both the relevant topic identifier and the complete answer-bearing sentence, including any condition or exception in that sentence. All 5 posts must pass this check.



**Why this target:**
The current campus posts are only 178–549 characters long, so preserving an answer with its context should be feasible. A phrase such as “three days” is not useful without knowing it concerns west-lot permits. This check tests the produced chunks directly, independently of whether retrieval finds them, and protects against losing context when I change the chunker.


---

## 5. Your choice

For at least 4 of my 5 test questions, the system must produce an answer that directly addresses the question and whose factual claims are all supported by the documents it cites. A refusal, incorrect answer, or answer containing an unsupported factual claim fails that question.


**Why this target:**
A filename alone does not establish that an answer is grounded. These documents contain distinctions that matter, including credit-hour priority versus random selection and dropping a course versus receiving a W. Four of five requires mostly accurate, supported answers while leaving room to investigate one failure.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 2 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 1. Retrieved chunks contain the answer

         For at least 4 of my 5 test questions, the retrieved chunks include
         one that contains the answer.

         **Why this target:** ...

         > **Revised in unit 2:** For at least 4 of 5 questions, the top three
         > results contain the answer.
         >
         > **Why revised:** I couldn't judge "the chunks include one that
         > contains the answer" the same way twice — I scored two questions
         > differently on Monday than on Wednesday. The new version is
         > something I can actually check.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said 4 of 5 but got 2 of 5, so 2 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.

     The whole reason the originals stay visible is so someone can see what you
     said before you knew the answer.
     ───────────────────────────────────────────────────────────────────────── -->
