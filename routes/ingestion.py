import os
import json
from flask import Blueprint, request, render_template, current_app
from werkzeug.utils import secure_filename
from utils.extractor import extract_text_from_pdf, extract_text_from_pptx
from utils.llm_groq import estimate_study_times_with_groq

ingestion_bp = Blueprint("ingestion", __name__, template_folder="../templates")
CURRICULUM_FILE = "curriculum.json"

@ingestion_bp.route("/", methods=["GET", "POST"])
def index():
    results = []

    if os.path.exists(CURRICULUM_FILE):
        with open(CURRICULUM_FILE, "r") as f:
            try:
                results = json.load(f)
            except:
                results = []

    if request.method == "POST":
        files = request.files.getlist("file")
        for file in files:
            filename = secure_filename(file.filename)
            path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(path)

            if filename.endswith(".pdf"):
                _, page_count = extract_text_from_pdf(path)
            elif filename.endswith(".pptx"):
                _, page_count = extract_text_from_pptx(path)
            else:
                continue

            course = estimate_study_times_with_groq(filename, page_count)
            results.append(course)

        with open(CURRICULUM_FILE, "w") as f:
            json.dump(results, f, indent=2)

    return render_template("upload_curriculum.html", curriculum=results)
