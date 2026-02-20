from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
import json
import os

load_dotenv()

from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html", user_name="Vikas")


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def build_system_prompt(memory):
    profile_text = json.dumps(memory, indent=2)
    return f"""You are a personal assistant for {memory.get('name', 'the user')}. 
You have access ONLY to the following personal details of the user.
Use ONLY this information when answering questions, generating letters, documents, or any content.
Do NOT invent, assume, or use any information that is not provided below.
If something is not available in the data, tell the user that the information is missing and ask them to provide it.

When asked to create documents like leave letters, applications, emails, etc., use the personal details below to fill in the relevant fields.

=== USER PERSONAL DATA ===
{profile_text}
=== END OF DATA ===

IMPORTANT: If the user tells you any new personal information about themselves (like their email, phone, address, company, college, etc.), you MUST respond normally AND include a JSON block at the very end of your response in this exact format:
[MEMORY_UPDATE]
{{"key": "value", "key2": "value2"}}
[/MEMORY_UPDATE]
Only include the fields that are new or changed. Use snake_case keys. Do NOT include this block if no new personal info was shared.

Always be helpful, polite, and generate well-formatted responses."""


def extract_memory_update(reply):
    """Extract and remove memory update block from the reply."""
    import re
    pattern = r'\[MEMORY_UPDATE\]\s*(\{.*?\})\s*\[/MEMORY_UPDATE\]'
    match = re.search(pattern, reply, re.DOTALL)
    if match:
        try:
            updates = json.loads(match.group(1))
            clean_reply = re.sub(pattern, '', reply, flags=re.DOTALL).strip()
            return clean_reply, updates
        except json.JSONDecodeError:
            pass
    return reply, None


@app.route("/")
def index():
    memory = load_memory()
    return render_template("index.html", user_name=memory.get("name", ""))


@app.route("/upload", methods=["POST"])
def upload_json():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename.endswith(".json"):
        return jsonify({"error": "Only JSON files are allowed"}), 400

    try:
        data = json.load(file)
        memory = load_memory()
        memory.update(data)
        save_memory(memory)
        return jsonify({"message": "Profile updated!", "data": memory})
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file"}), 400


@app.route("/chat", methods=["POST"])
def chat():
    memory = load_memory()
    if not memory:
        return jsonify({"error": "No memory found. Please tell me about yourself or upload a JSON."}), 400

    body = request.get_json()
    user_message = body.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    system_prompt = build_system_prompt(memory)

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.7,
                "max_tokens": 2048,
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        reply = result["choices"][0]["message"]["content"]

        # Check if model detected new personal info
        clean_reply, updates = extract_memory_update(reply)
        if updates:
            memory.update(updates)
            save_memory(memory)
            return jsonify({"reply": clean_reply, "memory_updated": True, "memory": memory})

        return jsonify({"reply": clean_reply})
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot connect to Groq API. Check your internet."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/profile", methods=["GET"])
def get_profile():
    memory = load_memory()
    return jsonify({"data": memory if memory else None})


@app.route("/profile/update", methods=["POST"])
def update_profile():
    body = request.get_json()
    if not body:
        return jsonify({"error": "No data provided"}), 400
    memory = load_memory()
    memory.update(body)
    save_memory(memory)
    return jsonify({"message": "Memory updated!", "data": memory})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
