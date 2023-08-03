import json

import puzzlepull

from flask import Flask, request, jsonify, Response

app = Flask(__name__)


@app.route("/")
def home():
    """Display homepage"""

    return "Hello world!", 200


@app.route("/guardian")
def guardian_puzzle():
    """Scrape a puzzle from the Guardian website and
    convert to .ipuz (JSON) format."""

    url = request.args.get("puzzle_url")
    download = request.args.get("download")
    if not download or download.lower() == "false":
        download = False
    else:
        download = True
    print(f"The URL provided is: {url}")

    puzzle = puzzlepull.get_guardian_puzzle(url, download=False)

    if download:
        return Response(
            json.dumps(puzzle),
            mimetype="application/json",
            headers={"Content-Disposition":
                     f"attachment;filename={puzzle['annotation']}"})
    else:
        return jsonify(puzzle), 200
