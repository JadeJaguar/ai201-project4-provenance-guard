# Provenance Guard

A backend system that classifies submitted text as likely AI generated, likely human written, or uncertain. It returns a confidence score, a plain language transparency label, and supports appeals from creators who think they were misclassified.

## How It Works

A creator submits a piece of text to `POST /submit`. The text is checked by two signals. The first signal asks an LLM (Groq) to judge if the text reads as human or AI. The second signal runs stylometric heuristics, pure math on the text itself, no external calls. Both scores are combined into one confidence score. That score decides the attribution category and the label text shown to the user. Every submission is written to a structured audit log. If a creator disagrees with the result, they can file an appeal through `POST /appeal`, which changes the status to under review and logs their reasoning next to the original decision.

## Detection Signals

**Signal 1: LLM check (Groq, weight 0.6)**

This signal sends the text to the Groq model and asks it to score how much the writing reads as AI generated, from 0 to 1. It captures meaning and style as a whole. It can notice things like generic phrasing, repeated structure, or topic patterns that a script cannot easily measure. Its blind spot is that it can be wrong with confidence. It gives a single number with no explanation, and a well written human paragraph that uses formal language can score high simply because it sounds polished.

**Signal 2: Stylometric heuristics (pure Python, weight 0.4)**

This signal measures two things directly from the text. First, sentence length variance, since AI writing tends to keep sentences closer to the same length. Second, type token ratio, which is unique words divided by total words, since AI writing tends to repeat words more than human writing. Both numbers are combined into one score. This signal is fully explainable, since every part of the score can be traced back to a specific measurement. Its blind spot is that it only looks at structure, not meaning. A short text with few sentences gives an unreliable variance number, and a human writer who happens to write in a very uniform style can score high by accident.

We picked these two because they measure different things. One is semantic, the other is structural. We saw this play out directly during testing. A test text written to be obviously AI generated got a 0.9 from the LLM signal but only 0.0655 from the stylometric signal, because one of its sentences was much longer than the others. That single disagreement pulled the combined score down into the uncertain range instead of likely AI. That is the system being honest about a real disagreement between two independent ways of looking at the same text, not the system failing.

## Confidence Scoring and Uncertainty

The combined score is:

```
confidence = (llm_score * 0.6) + (stylometric_score * 0.4)
```

We weighted the LLM signal higher because it tends to be the stronger general purpose detector, but kept the stylometric signal at 0.4 so a strong disagreement between the two can still pull a result toward uncertain.

Thresholds:

| Confidence range | Attribution |
|---|---|
| 0.00 to 0.40 | likely_human |
| 0.41 to 0.65 | uncertain |
| 0.66 to 1.00 | likely_ai |

The middle range is wide on purpose. A false positive, calling a human's work AI generated, is worse than a false negative on a creative platform. A wide uncertain band means borderline cases land in a category that tells the reader to use their own judgment, instead of being forced into a confident label that might be wrong.

**Example submissions showing real score variation:**

High confidence example:
Text: a deliberately AI sounding paragraph about artificial intelligence and stakeholders.
Result: confidence 0.8, attribution likely_ai

Lower confidence example:
Text: "ok so i finally tried that new ramen place downtown and honestly underwhelming, the broth was fine but way too salty"
Result: confidence 0.2, attribution likely_human

We also tested a case where the two signals disagreed sharply, described above, and that case produced confidence 0.5662, attribution uncertain. We consider this a working example of the scoring system, not a failure, since it shows the score moving away from a confident label exactly when the underlying evidence is mixed.

To check that scores were meaningful and not just noise, we ran four deliberately different inputs through the system together: a clearly AI sounding paragraph, a clearly casual human paragraph, a formal but human written paragraph, and a lightly edited AI paragraph. The four scores were not identical, and the two clearly different inputs (obvious AI text and casual human text) produced the largest gap between them, which is what we expected.

## Transparency Label

The label text changes based on the attribution category. Here are the three exact variants:

**Likely AI generated:**
"This content is likely AI generated. Our system found a confidence score of {confidence} based on multiple signals."

**Likely human written:**
"This content is likely written by a human. Our system found a confidence score of {confidence} based on multiple signals."

**Uncertain:**
"We are not confident whether this content is AI generated or human written. The confidence score was {confidence}, which falls in our uncertain range. Please use your own judgment."

`{confidence}` is replaced with the actual numeric score in every response.

## Appeals Workflow

Any creator can appeal a classification by sending the content_id from their original submission, along with their reasoning, to `POST /appeal`. The system:

1. Looks up the original log entry by content_id.
2. Updates its status to `under_review`.
3. Logs the appeal reasoning and an appeal timestamp directly on that same entry, next to the original decision data.
4. Returns a confirmation message to the creator.

If the content_id does not exist, the endpoint returns a 404 error. If either field is missing, it returns a 400 error. Automated re-classification is not implemented. A human reviewer opening the appeal queue would see the full original entry (signals, confidence, attribution) sitting right next to the creator's reasoning, since both live in the same log entry.

Example appeal log entry, captured during testing:

```
appeal_reasoning  : I wrote this myself, it is based on a real memory.
appeal_timestamp  : 2026-06-30T22:45:22.210340Z
attribution       : likely_human
confidence        : 0.32
content_id        : a97016ce-85da-4fcb-bc90-8dcacbf5de56
creator_id        : test-m5-d
llm_score         : 0.2
status            : under_review
stylometric_score : 0.5
timestamp         : 2026-06-30T22:45:20.168693Z
```

## Rate Limiting

The submit endpoint is limited to 10 requests per minute and 100 per day, per IP address, using Flask-Limiter with in memory storage.

Reasoning: a real creator submitting their own work would rarely post more than a few pieces in a single minute. 10 per minute leaves room for normal use and for testing, while still blocking a script that tries to flood the endpoint quickly. 100 per day covers a very active user across a full day without allowing abuse at scale.

Evidence the limit works, from sending 12 rapid requests in a row:

```
200
200
200
200
200
200
200
200
200
429
429
429
```

The first 9 requests succeeded. After that, the server started returning 429, meaning the limit was reached and further requests were rejected.

## Audit Log

Every submission and every appeal is written as a structured entry to `audit_log.json`, viewable through `GET /log`. Each entry includes the timestamp, content_id, creator_id, attribution, confidence, both individual signal scores, and status. Appeal entries add appeal_reasoning and appeal_timestamp on top of the original fields.

Sample entries from testing:

```json
{
  "content_id": "207c4a64-fc63-4e66-b3f9-4065a43b9aad",
  "creator_id": "test-m4-a",
  "timestamp": "2026-06-30T22:29:21.959978Z",
  "attribution": "uncertain",
  "confidence": 0.5662,
  "llm_score": 0.9,
  "stylometric_score": 0.0655,
  "status": "classified"
}
```

```json
{
  "content_id": "926ec227-3054-4212-97c3-efacd477ea85",
  "creator_id": "label-test",
  "timestamp": "2026-06-30T22:36:10.000000Z",
  "attribution": "likely_human",
  "confidence": 0.2,
  "llm_score": 0.0,
  "stylometric_score": 0.5,
  "status": "classified"
}
```

```json
{
  "appeal_reasoning": "I wrote this myself, it is based on a real memory.",
  "appeal_timestamp": "2026-06-30T22:45:22.210340Z",
  "attribution": "likely_human",
  "confidence": 0.32,
  "content_id": "a97016ce-85da-4fcb-bc90-8dcacbf5de56",
  "creator_id": "test-m5-d",
  "llm_score": 0.2,
  "status": "under_review",
  "stylometric_score": 0.5,
  "timestamp": "2026-06-30T22:45:20.168693Z"
}
```

## Known Limitations

The stylometric signal can be wrong on short or unevenly structured text, even when the text is clearly AI generated. We saw this directly in testing. A paragraph written to sound obviously AI generated had one sentence much longer than the other two. That high sentence length variance is normally a sign of human writing in our heuristic, so the stylometric signal scored it as strongly human (0.0655) while the LLM signal scored it as strongly AI (0.9). The disagreement pulled the combined score down to uncertain. This is a real blind spot of measuring only sentence structure: a single irregular sentence in an otherwise uniform AI generated text can flip the stylometric reading.

A second likely weak spot is very short submissions. The stylometric signal needs several sentences to compute a meaningful variance number. A short poem or a one or two sentence excerpt does not give the heuristic much to work with, so its score on short text is less reliable than on longer passages.

## Stretch Features

### Ensemble Detection

We extended the pipeline from two signals to three. The new third signal is punctuation and structure heuristics, separate from the original stylometric signal. It measures two things in pure Python: punctuation density (commas, semicolons, and colons divided by total words), and how often consecutive sentences start with the same word or phrase. AI writing tends to use denser punctuation and repeat structural openers more than human writing does.

We chose this as a third signal because it looks at different specific features than our existing stylometric signal, even though both are structural rather than semantic. Two structural signals that agree with each other give us more confidence than one structural signal alone, while the LLM signal still captures meaning and style that neither structural signal can see.

The weighting formula changed from a two-signal average to:

```
confidence = (llm_score * 0.5) + (stylometric_score * 0.3) + (punctuation_score * 0.2)
```

We lowered the LLM weight slightly and split the rest across both structural signals, so two structural signals agreeing can meaningfully move the score without letting the LLM dominate the result outright.

To confirm the new signal works as intended, we tested it against a paragraph built specifically to repeat sentence openers ("It is clear that..." three times in a row) and compared it to a casual, varied human paragraph. The repeated-opener text scored 0.4 on the punctuation and structure signal, while the casual text scored 0.0, confirming the repeat-opener detection is functioning. We also re-ran our original clearly-AI and clearly-human test texts through the new three-signal formula and confirmed the scores still varied meaningfully (0.5069 vs 0.1191), the same kind of spread we saw with the two-signal version.

### Analytics Dashboard

We added a `GET /analytics` endpoint that reads the existing audit log and returns summary statistics, without collecting any new data. It returns:

1. **Attribution breakdown**: count and percent of submissions in each category (likely_human, uncertain, likely_ai).
2. **Appeal rate**: percent of total submissions with status under_review.
3. **Average confidence**: the mean confidence score across all submissions.

We kept this as a JSON endpoint rather than a visual dashboard, consistent with the rest of the API and simple enough to satisfy the "simple view" requirement.

Sample output, captured during testing with 32 total submissions:

```json
{
  "appeal_rate": 6.25,
  "attribution_breakdown": {
    "likely_ai": {"count": 2, "percent": 6.25},
    "likely_human": {"count": 23, "percent": 71.88},
    "uncertain": {"count": 7, "percent": 21.88}
  },
  "average_confidence": 0.3155,
  "total_submissions": 32
}
```

The category counts (2 + 23 + 7 = 32) match total_submissions, and the percentages sum to roughly 100, confirming the math is internally consistent.

## Spec Reflection

Writing planning.md before any code helped most with the confidence scoring section. Deciding on the weights (0.6 and 0.4) and the three thresholds before writing a single line of scoring code meant the implementation was a direct translation of a decision we had already made, instead of something we had to figure out while staring at code.

One place implementation diverged from the spec was the stylometric signal. The plan described it generally as measuring sentence length variance and vocabulary diversity, but did not specify exact formulas. During building, we had to decide how to scale variance into a 0 to 1 score and how to weigh it against type token ratio. Those exact formulas were worked out during implementation rather than in planning.md, since some of that detail only became clear once we saw real numbers come out of test text.

## AI Usage

We used AI assistance in two specific ways during this project.

First, for Milestone 3, we gave the AI tool our detection signals section from planning.md along with the architecture diagram, and asked it to generate the Flask app skeleton and the first signal function (the Groq call). The generated function signature matched our spec. We tested it independently with sample text before wiring it into the submit endpoint, which is how we confirmed it returned a usable score before depending on it elsewhere.

Second, for Milestone 5, we asked the AI tool to generate the label function and the appeal endpoint, using the label variants and appeals workflow sections of planning.md. The first version placed the label generation line before the line that calculated the attribution category, which caused an UnboundLocalError at runtime, since the label function needed a value that had not been created yet. We fixed this by moving the label line to after the attribution block, so it would run with the correct value available.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with:

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Run the tests, with the app running in a separate terminal:

```bash
python tests/test_milestone3.py
python tests/test_milestone4.py
python tests/test_milestone5.py
```

## API Endpoints

`POST /submit` - accepts `text` and `creator_id`, returns content_id, attribution, confidence, and label.

`GET /log` - returns all audit log entries.

`POST /appeal` - accepts `content_id` and `creator_reasoning`, returns confirmation and updates the log entry's status to under_review.

`GET /analytics` - returns attribution breakdown, appeal rate, and average confidence, calculated from the audit log. (stretch feature)