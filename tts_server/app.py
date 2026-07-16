import asyncio
import os
import tempfile

import edge_tts
from aip import AipSpeech
from flask import Flask, Response, jsonify, request
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"
BAIDU_APP_ID = os.environ.get("BAIDU_APP_ID", "27580703")
BAIDU_API_KEY = os.environ.get("BAIDU_API_KEY", "t6P4PgHeEMB9toRHunzITJ92")
BAIDU_SECRET_KEY = os.environ.get("BAIDU_SECRET_KEY", "0yFT4gNBTDhKgAGX5HBExeIWenLdRmYL")
baidu_client = AipSpeech(BAIDU_APP_ID, BAIDU_API_KEY, BAIDU_SECRET_KEY)


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


@app.post("/api/speech-to-text")
def speech_to_text():
    audio_file = request.files.get("audio") or request.files.get("file")
    if not audio_file:
        return jsonify({"success": False, "error": "audio file is required"}), 400

    audio_data = audio_file.read()
    audio_format = (request.form.get("format") or "wav").lower()
    rate = int(request.form.get("rate") or 16000)

    if audio_format.startswith("audio/"):
        audio_format = audio_format.split("/", 1)[1]
    if audio_format == "x-wav":
        audio_format = "wav"

    try:
        result = baidu_client.asr(audio_data, audio_format, rate, {
            "dev_pid": 1537,
            "channel": 1,
        })
        if result.get("err_no") == 0:
            return jsonify({
                "success": True,
                "text": "".join(result.get("result", [])),
                "raw_result": result.get("result", []),
                "sn": result.get("sn", ""),
            })
        return jsonify({
            "success": False,
            "text": "",
            "error": result.get("err_msg", "speech recognition failed"),
            "err_no": result.get("err_no"),
        }), 422
    except Exception as exc:
        return jsonify({"success": False, "text": "", "error": str(exc)}), 500


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
