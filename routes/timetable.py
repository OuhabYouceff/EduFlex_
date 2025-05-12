import os
import json
import base64
import re
from flask import Blueprint, request, render_template
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
from PIL import Image
from io import BytesIO
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dateutil import tz
from utils.calendar import add_event
from groq import Groq

# Ensure upload folder exists
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load .env
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def image_to_base64(image):
    """
    Convert a PIL image to base64 string after ensuring it's in a JPEG-compatible format.
    """
    try:
        # Convert RGBA to RGB if necessary (JPEG doesn't support transparency)
        if image.mode == "RGBA":
            image = image.convert("RGB")
        
        # Save the image to a buffer in JPEG format
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        
        # Encode the image to base64
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return img_str
    except Exception as e:
        raise Exception(f"Error converting image to base64: {str(e)}")

def pdf_to_image(pdf_path):
    """
    Convert a PDF file to a PIL image.
    """
    try:
        images = convert_from_path(pdf_path)
        return images[0]  # Return the first page
    except Exception as e:
        raise Exception(f"Error converting PDF to image: {str(e)}")

def call_groq_vision(image_base64):
    """
    Call Groq's vision API to extract timetable data from the image.
    """
    prompt = (
        "Extract the day of the week, subject name, start time, and end time from this timetable image. "
        "The morning session always ends at 12:15. "
        "Return the output strictly as a JSON object with days as keys ('Lundi', 'Mardi', etc), and values as lists of sessions.\n\n"
        "Each session must be an object like: {\"matiere\": \"subject name\", \"start\": \"HH:MM\", \"end\": \"HH:MM\"}.\n\n"
        "If there are no sessions for a day, return an empty list for that day.\n"
        "Always include all 7 days from 'Lundi' to 'Dimanche'."
    )

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }
            ],
            temperature=1,
            max_completion_tokens=1024,
            top_p=1,
            stream=False,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Groq Error: {e}")
        return ""

def extract_json(text):
    """
    Extract and parse JSON from the raw text response.
    """
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        json_block = text[start:end]
        json_block = re.sub(r"(?<!\\)'", '"', json_block)
        return json.loads(json_block)
    except Exception as e:
        print(f"⚠️ JSON parsing failed: {e}")
        return {}

def get_next_monday():
    """
    Get the date of the next Monday.
    """
    today = datetime.now()
    return today + timedelta(days=(7 - today.weekday()) % 7)

def insert_into_calendar(schedule):
    """
    Insert the extracted timetable sessions into a calendar.
    """
    DAYS = {
        "Lundi": 0,
        "Mardi": 1,
        "Mercredi": 2,
        "Jeudi": 3,
        "Vendredi": 4,
        "Samedi": 5,
        "Dimanche": 6
    }

    local_tz = tz.gettz("Europe/Paris")
    monday = get_next_monday()

    for day, sessions in schedule.items():
        offset = DAYS.get(day, 0)
        course_date = monday + timedelta(days=offset)

        for session in sessions:
            try:
                start_time = datetime.strptime(session["start"], "%H:%M").time()
                end_time = datetime.strptime(session["end"], "%H:%M").time()
                subject = session.get("matiere", "Cours")

                naive_start = datetime.combine(course_date.date(), start_time)
                naive_end = datetime.combine(course_date.date(), end_time)

                start_dt = naive_start.replace(tzinfo=local_tz)
                end_dt = naive_end.replace(tzinfo=local_tz)

                add_event(f"📚 {subject}", start_dt, end_dt)

            except Exception as e:
                print(f"❌ Error parsing session for {day}: {e}")

timetable_bp = Blueprint("timetable", __name__, template_folder="../templates")

@timetable_bp.route("/", methods=["GET", "POST"])
def index():
    timetable = {}

    if request.method == "POST":
        # Check if a file is uploaded
        if "file" not in request.files:
            print("⚠️ No file part in the request.")
            return render_template("timetable.html", timetable=timetable, error="No file uploaded.")

        file = request.files["file"]
        if not file or file.filename == "":
            print("⚠️ No file selected.")
            return render_template("timetable.html", timetable=timetable, error="No file selected.")

        # Save the uploaded file
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        try:
            # Convert to image based on file type
            if filename.lower().endswith(".pdf"):
                image = pdf_to_image(path)
            else:
                image = Image.open(path).convert("RGB")  # Ensure RGB mode for images

            # Convert image to base64
            base64_img = image_to_base64(image)

            # Call vision model to extract timetable
            raw_response = call_groq_vision(base64_img)
            timetable = extract_json(raw_response)

            if timetable:
                insert_into_calendar(timetable)
            else:
                print("⚠️ No valid timetable extracted.")
                return render_template("timetable.html", timetable=timetable, error="Failed to extract timetable.")

        except Exception as e:
            print(f"❌ Processing error: {e}")
            return render_template("timetable.html", timetable=timetable, error=f"Error processing file: {str(e)}")

        finally:
            # Clean up: Remove the uploaded file
            if os.path.exists(path):
                os.remove(path)

    return render_template("timetable.html", timetable=timetable)