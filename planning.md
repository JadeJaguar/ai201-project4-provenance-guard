# Provenance Guard - Planning

## 1. Detection Signals

### Signal 1: Groq LLM Check
- What it measures: overall semantic and stylistic coherence. The model reads the text and judges if it sounds human written or AI generated.
- Output type: a score between 0 and 1, where 1 means strongly AI-like.
- Why it differs: AI text tends to be smooth and evenly paced. Human text tends to have small inconsistencies and personal detail.
- Blind spot: it can be fooled by AI text that was lightly edited by a human. It can also misjudge human writers who use a formal, structured style.

### Signal 2: Stylometric Heuristics
- What it measures: sentence length variance, vocabulary diversity (type-token ratio), and punctuation density.
- Output type: a score between 0 and 1, where 1 means strongly AI-like.
- Why it differs: AI text tends to have uniform sentence lengths and steady vocabulary use. Human text tends to be more irregular.
- Blind spot: it cannot read meaning or context. A human who writes in a plain, repetitive style can score close to AI text on this signal alone.

### Combining the Signals
- combined_score = (0.6 * llm_score) + (0.4 * stylo_score)
- The LLM signal gets more weight because it reads meaning, which is a stronger overall signal than structure alone. The stylometric signal still pulls the score down when the LLM is unsure.

## 2. Uncertainty Representation

- A score is a number between 0 and 1. 1 means very likely AI. 0 means very likely human.
- Thresholds:
  - 0.00 to 0.40: likely human
  - 0.41 to 0.65: uncertain
  - 0.66 to 1.00: likely AI
- The uncertain band is wide on purpose. Because a false positive (calling a human's work AI) is worse than a false negative, the system should only commit to "likely AI" when the score is clearly high.
- A score of 0.6 means the system leans slightly toward AI but is not confident enough to say so directly. The label for this score must say "uncertain," not "likely AI."

## 3. Transparency Label Variants

| Result | Label Text |
|---|---|
| High-confidence AI | "This content shows strong signs of AI generation. We're not 100% certain, but the patterns we detected are consistent with AI-written text." |
| High-confidence human | "This content shows strong signs of human authorship. Our checks found no significant indicators of AI generation." |
| Uncertain | "We could not confidently determine whether this content is AI-generated or human-written. Treat this result as inconclusive." |

## 4. Appeals Workflow

- Who can appeal: the original creator_id tied to the content.
- What they provide: content_id and a written reasoning explaining why they believe the classification is wrong.
- What the system does:
  - Updates the content's status to "under_review"
  - Logs the appeal as a new audit log entry, linked to the original content_id, including the original scores and the new reasoning
  - Returns a confirmation message to the creator
- What a human reviewer would see: the original submission text, both signal scores, the combined confidence score, the label that was shown, and the creator's appeal reasoning, all in one place via the audit log.

## 5. Anticipated Edge Cases

1. A human writer using a formal, academic tone (for example, a non-native English speaker writing in a textbook style) may score high on the stylometric signal because their sentence structure is uniform, even though the LLM signal correctly reads it as human.
2. A short piece of text, such as a two-sentence poem, may not give the stylometric signal enough data to compute meaningful variance. Short inputs should be treated as lower-confidence results.

## Architecture

```
SUBMISSION FLOW

[Creator]
   |
   | POST /submit
   | { text, creator_id }
   v
[Flask API: /submit endpoint]
   |
   | raw text
   v
[Signal 1: Groq LLM Check] --llm_score-->
   v
[Signal 2: Stylometric Heuristics] --stylo_score-->
   v
[Confidence Scoring] --confidence_score-->
   v
[Label Generator] --label_text-->
   v
[Audit Log]
   v
[Response to Creator]
   { content_id, attribution, confidence_score, label_text }


APPEAL FLOW

[Creator]
   |
   | POST /appeal
   | { content_id, creator_reasoning }
   v
[Flask API: /appeal endpoint]
   v
[Status Update -> "under_review"]
   v
[Audit Log]
   v
[Response to Creator]
   { content_id, status, message }
```

Submission flow: a creator submits text, it passes through both detection signals, the scores are combined into a confidence score, a label is picked based on that score, and everything is logged before the response goes back.

Appeal flow: a creator submits a content_id and their reasoning, the content's status changes to under_review, the appeal is logged next to the original decision, and a confirmation is sent back.

## AI Tool Plan

### M3: Submission endpoint + first signal
- Spec sections to give the AI tool: Detection Signals (Signal 1 only), Architecture diagram
- What to ask for: Flask app skeleton with POST /submit route stub, plus the Groq LLM signal function
- How to verify: call the signal function directly with 2-3 test inputs and check the output before wiring it into the route

### M4: Second signal + confidence scoring
- Spec sections to give the AI tool: Detection Signals (both), Uncertainty Representation, Architecture diagram
- What to ask for: stylometric signal function, plus the confidence scoring function that combines both signals
- How to verify: test the combined score on a clearly AI text and a clearly human text, confirm the scores are meaningfully different

### M5: Production layer
- Spec sections to give the AI tool: Transparency Label Variants, Appeals Workflow, Architecture diagram
- What to ask for: label generation function, POST /appeal endpoint
- How to verify: test that all three label variants are reachable at different score ranges, test that an appeal updates status and appears in the log correctly

## Stretch Features

### Ensemble Detection (3+ signals)

We will add a third detection signal to move from two signals to an ensemble of three.

Third signal: punctuation and structure heuristics. This measures two things in pure Python, separate from our existing stylometric signal. First, punctuation density, the ratio of punctuation marks (commas, semicolons, colons) to total words. AI writing tends to use comma-heavy, evenly structured sentences. Second, repeated sentence openers, how often consecutive sentences start with the same word or phrase (for example, "It is important" appearing twice). AI writing tends to repeat structural patterns like this more than human writing does. Both numbers are combined into one score between 0 and 1, the same way our existing stylometric signal works.

We chose this as our third signal because it is structural, like our stylometric signal, but looks at different features of the text (punctuation and repetition, rather than sentence length variance and vocabulary diversity). This gives us three signals that are not fully independent in category (two structural, one semantic) but are independent in what specific feature each one measures.

Weighting approach: we are moving from a two-signal weighted average to a three-signal weighted average.

New weights: Groq LLM signal 0.5, stylometric signal 0.3, punctuation and structure signal 0.2.

We lowered the LLM weight slightly and split the remaining weight across our two structural signals, since adding a third signal that agrees with the second structural signal should increase our confidence when both structural signals agree, without letting the LLM signal dominate the result entirely.

Formula:
confidence = (llm_score * 0.5) + (stylometric_score * 0.3) + (punctuation_score * 0.2)

We will re-test our four original example texts (clearly AI, clearly human, two borderline cases) with the new three-signal formula to confirm scores still vary meaningfully and the new signal does not break our existing threshold ranges.

### Analytics Dashboard

We will add a new endpoint, GET /analytics, that reads the existing audit log and returns summary statistics. No new data needs to be collected, since the audit log already has everything needed (attribution, confidence, status, appeal data).

Metrics to include:

1. Attribution breakdown: count and percent of submissions in each category (likely_human, uncertain, likely_ai).
2. Appeal rate: percent of total submissions that have been appealed (status is under_review).
3. Average confidence score: the mean confidence score across all submissions, to show the overall lean of the system.

This endpoint will return the data as JSON, in the same style as our existing GET /log endpoint. We are not building a visual dashboard with charts, since the project only asks for a simple view, and a JSON summary endpoint satisfies that while staying consistent with the rest of our API design.