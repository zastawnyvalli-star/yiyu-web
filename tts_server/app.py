import asyncio
import os
import tempfile

import edge_tts
from flask import Flask, Response, jsonify, request
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


@app.get("/")
def health():
    return jsonify({"ok": True, "service": "yiyu-tts", "voice": DEFAULT_VOICE})


@app.post("/api/tts")
def tts():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    voice = data.get("voice") or DEFAULT_VOICE

    if not text:
        return jsonify({"success": False, "error": "text is required"}), 400

    if len(text) > 1200:
        text = text[:1200]

    try:
        audio_data = asyncio.run(synthesize(text, voice))
        return Response(
            audio_data,
            mimetype="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=tts.mp3",
                "Content-Length": str(len(audio_data)),
            },
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


async def synthesize(text, voice):
    communicate = edge_tts.Communicate(text, voice)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        path = tmp.name

    try:
        await communicate.save(path)
        with open(path, "rb") as audio_file:
            return audio_file.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
