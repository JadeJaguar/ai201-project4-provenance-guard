import os
import json
import uuid
import datetime
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

LOG_FILE = "audit_log.json"


def read_log():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        return json.load(f)


def write_log_entry(entry):
    log = read_log()
    log.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

def update_log_entry(content_id, updates):
    log = read_log()
    found = False
    for entry in log:
        if entry.get("content_id") == content_id:
            entry.update(updates)
            found = True
            break
    if found:
        with open(LOG_FILE, "w") as f:
            json.dump(log, f, indent=2)
    return found

def signal_stylometric(text):
    import re

    words = text.split()
    word_count = len(words)

    if word_count == 0:
        return 0.5

    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sentence_count = len(sentences)

    if sentence_count == 0:
        return 0.5

    sentence_lengths = [len(s.split()) for s in sentences]
    mean_length = sum(sentence_lengths) / len(sentence_lengths)
    variance = sum((l - mean_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)

    unique_words = set(w.lower().strip(".,!?;:\"'") for w in words)
    type_token_ratio = len(unique_words) / word_count

    low_variance_score = max(0.0, min(1.0, 1.0 - (variance / 30.0)))
    low_diversity_score = max(0.0, min(1.0, 1.0 - type_token_ratio))

    score = (low_variance_score * 0.5) + (low_diversity_score * 0.5)
    return round(score, 4)

def get_label(confidence, attribution):
    if attribution == "likely_ai":
        return (
            "This content is likely AI generated. Our system found a "
            f"confidence score of {confidence} based on multiple signals."
        )
    elif attribution == "likely_human":
        return (
            "This content is likely written by a human. Our system found a "
            f"confidence score of {confidence} based on multiple signals."
        )
    else:
        return (
            "We are not confident whether this content is AI generated or "
            f"human written. The confidence score was {confidence}, which falls "
            "in our uncertain range. Please use your own judgment."
        )

def signal_punctuation_structure(text):
    import re

    words = text.split()
    word_count = len(words)

    if word_count == 0:
        return 0.5

    punctuation_marks = re.findall(r'[,;:]', text)
    punctuation_density = len(punctuation_marks) / word_count

    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) < 2:
        return 0.5

    openers = []
    for sentence in sentences:
        words_in_sentence = sentence.split()
        if words_in_sentence:
            openers.append(words_in_sentence[0].lower())

    repeated_openers = 0
    for i in range(1, len(openers)):
        if openers[i] == openers[i - 1]:
            repeated_openers += 1

    repeat_ratio = repeated_openers / (len(openers) - 1) if len(openers) > 1 else 0

    high_punctuation_score = max(0.0, min(1.0, punctuation_density / 0.15))
    repeat_opener_score = max(0.0, min(1.0, repeat_ratio * 2))

    score = (high_punctuation_score * 0.6) + (repeat_opener_score * 0.4)
    return round(score, 4)


def signal_llm(text):
    prompt = (
        "You are an expert at spotting AI generated text.\n"
        "Read the text below. Give a score from 0 to 1.\n"
        "0 means you are sure a human wrote it.\n"
        "1 means you are sure AI wrote it.\n"
        "Only reply with the number. No words.\n\n"
        f"Text:\n{text}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"WARNING: Groq API call failed, falling back to neutral score. Error: {e}")
        return 0.5

    try:
        score = float(raw)
    except ValueError:
        score = 0.5

    score = max(0.0, min(1.0, score))
    return score

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json()
    text = data.get("text", "")
    creator_id = data.get("creator_id", "unknown")

    content_id = str(uuid.uuid4())
    llm_score = signal_llm(text)
    stylometric_score = signal_stylometric(text)
    punctuation_score = signal_punctuation_structure(text)

    confidence = round(
        (llm_score * 0.5) + (stylometric_score * 0.3) + (punctuation_score * 0.2), 4
    )
    if confidence <= 0.40:
        attribution = "likely_human"
    elif confidence <= 0.65:
        attribution = "uncertain"
    else:
        attribution = "likely_ai"

    label = get_label(confidence, attribution)
    
    entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylometric_score,
        "punctuation_score": punctuation_score,
        "status": "classified",
    }
    write_log_entry(entry)

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json()
    content_id = data.get("content_id", "")
    creator_reasoning = data.get("creator_reasoning", "")

    if not content_id or not creator_reasoning:
        return jsonify({"error": "content_id and creator_reasoning are both required"}), 400

    updates = {
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
        "appeal_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

    found = update_log_entry(content_id, updates)

    if not found:
        return jsonify({"error": "content_id not found"}), 404

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal received and logged for review",
    })

@app.route("/log", methods=["GET"])
def log():
    return jsonify({"entries": read_log()})

@app.route("/analytics", methods=["GET"])
def analytics():
    log = read_log()
    total = len(log)

    if total == 0:
        return jsonify({
            "total_submissions": 0,
            "attribution_breakdown": {},
            "appeal_rate": 0,
            "average_confidence": 0,
        })

    attribution_counts = {"likely_human": 0, "uncertain": 0, "likely_ai": 0}
    appealed_count = 0
    confidence_sum = 0

    for entry in log:
        attribution = entry.get("attribution")
        if attribution in attribution_counts:
            attribution_counts[attribution] += 1

        if entry.get("status") == "under_review":
            appealed_count += 1

        confidence_sum += entry.get("confidence", 0)

    attribution_breakdown = {}
    for category, count in attribution_counts.items():
        attribution_breakdown[category] = {
            "count": count,
            "percent": round((count / total) * 100, 2),
        }

    appeal_rate = round((appealed_count / total) * 100, 2)
    average_confidence = round(confidence_sum / total, 4)

    return jsonify({
        "total_submissions": total,
        "attribution_breakdown": attribution_breakdown,
        "appeal_rate": appeal_rate,
        "average_confidence": average_confidence,
    })

if __name__ == "__main__":
    app.run(debug=True)