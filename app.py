import os
from flask import Flask, jsonify, render_template, request

from simplex_solver import solve_payload

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/solve", methods=["POST"])
def solve():
    try:
        payload = request.get_json(force=True)
        result = solve_payload(payload)
        return jsonify(result)
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc)
        }), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)