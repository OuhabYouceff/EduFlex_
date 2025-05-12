import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template
from utils.llm_groq import generate_study_plan
from utils.calendar import get_free_slots, add_event

planner_bp = Blueprint("planner", __name__, template_folder="../templates")

@planner_bp.route("/planner", methods=["GET"])
def planner():
    if not os.path.exists("curriculum.json"):
        return "❌ No curriculum found. Please upload one first.", 400

    with open("curriculum.json", "r") as f:
        curriculum = json.load(f)

    now = datetime.now().astimezone()
    monday = now - timedelta(days=now.weekday())  # this week's Monday
    sunday_next = monday + timedelta(days=13)     # end of next week

    free_slots = get_free_slots(monday, sunday_next)
    study_plan = generate_study_plan(curriculum, free_slots)

    if not study_plan:
        return "❌ No valid study plan returned by the LLM", 500

    for session in study_plan:
        try:
            title = session["course"]
            start = datetime.fromisoformat(session["start"])
            end = datetime.fromisoformat(session["end"])
            add_event(f"📖 Study: {title}", start, end)
        except Exception as e:
            print(f"⚠️ Failed to add event: {e}")
    open("curriculum.json", "w").write("[]")
    with open("sessions.json", "w") as f:
        json.dump([
            {
                "id": idx,
                "course": session["course"],
                "start": session["start"],
                "done": False
            } for idx, session in enumerate(study_plan)
        ], f, indent=2)

    return render_template("planning_result.html", study_plan=study_plan)
