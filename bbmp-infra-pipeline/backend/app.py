from flask import Flask, request, jsonify
import os
from ingestion.xml_parser import parse_xml, save_json

app = Flask(__name__)

UPLOAD_FOLDER = "../data/raw"
OUTPUT_FOLDER = "../data/processed"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


@app.route("/upload-xml", methods=["POST"])
def upload_xml():
    file = request.files["file"]

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    parsed = parse_xml(file_path)

    output_path = os.path.join(OUTPUT_FOLDER, "output.json")
    save_json(parsed, output_path)

    return jsonify({
        "message": "XML processed successfully",
        "output_file": output_path
    })


if __name__ == "__main__":
    app.run(debug=True)