import os
from flask import Flask, render_template
from dotenv import load_dotenv

from flask import Flask, render_template, request, session, redirect, url_for, flash
from datetime import datetime
from io import BytesIO
import fitz  # PyMuPDF
import json
import requests
import os
import uuid
import tempfile
# Load environment variables
load_dotenv()

# Init Flask app
app = Flask(__name__)

# Uploads folder
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Secret key for sessions
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())

# Import Blueprints
from routes.timetable import timetable_bp
from routes.ingestion import ingestion_bp
from routes.planner import planner_bp


# Register Blueprints with route prefixes
app.register_blueprint(timetable_bp, url_prefix="/timetable")
app.register_blueprint(ingestion_bp, url_prefix="/upload_curriculum")
app.register_blueprint(planner_bp)




# Main route
@app.route("/")
def home():
    return render_template("index.html")

# Directory for temporary files
TEMP_DIR = tempfile.gettempdir()

# === Fonctions utilitaires ===

def get_subject_from_schedule(json_file):
    if not os.path.exists(json_file):
        return None, None, None, None

    with open(json_file, "r") as f:
        schedule = json.load(f)

    now = datetime.now()
    current_date = now.strftime('%Y-%m-%d')
    current_day = now.strftime('%A').lower()
    current_hour = now.strftime('%H:%M')

    jour_map = {
        'monday': 'lundi',
        'tuesday': 'mardi',
        'wednesday': 'mercredi',
        'thursday': 'jeudi',
        'friday': 'vendredi',
        'saturday': 'samedi',
        'sunday': 'dimanche'
    }
    jour_fr = jour_map.get(current_day, "")

    if jour_fr in schedule:
        for session in schedule[jour_fr]:
            if session["debut"] <= current_hour <= session["fin"]:
                return current_date, jour_fr, current_hour, session["matiere"]

    return current_date, jour_fr, current_hour, None


def extract_text_from_pdf(pdf_file):
    try:
        doc = fitz.open(stream=pdf_file, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        return ""
    
def save_text_to_temp_file(text):
    file_id = str(uuid.uuid4())
    temp_file_path = os.path.join(TEMP_DIR, f"pdf_text_{file_id}.txt")
    with open(temp_file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return file_id, temp_file_path

def read_text_from_temp_file(file_id):
    temp_file_path = os.path.join(TEMP_DIR, f"pdf_text_{file_id}.txt")
    if os.path.exists(temp_file_path):
        with open(temp_file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def delete_temp_file(file_id):
    temp_file_path = os.path.join(TEMP_DIR, f"pdf_text_{file_id}.txt")
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

def generate_quiz_from_text(course_text):
    OLLAMA_URL = "http://localhost:11434/api/generate"
    MODEL_NAME = "llama3.2:latest"

    prompt = f"""
Tu es un professeur. Génére exactement 5 questions à choix multiples (QCM) à partir du texte suivant :

{course_text}

Chaque question doit suivre ce format strictement, sans aucun texte supplémentaire :

1. Question ?
A) option1
B) option2 ✅
C) option3
D) option4
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")
    except requests.exceptions.RequestException:
        return None
    
# === Routes ===

@app.route('/revision', methods=['GET', 'POST'])
def index():
    date, day, hour, subject = get_subject_from_schedule("calendrier.json")
    session['quiz_raw'] = session.get('quiz_raw', '')
    session['user_answers'] = session.get('user_answers', {})
    session['quiz_done'] = session.get('quiz_done', False)
    session['incorrect_questions'] = session.get('incorrect_questions', [])
    session['chat_history'] = session.get('chat_history', [])

    pdf_text_preview = ""
    if 'pdf_file_id' in session:
        pdf_text = read_text_from_temp_file(session['pdf_file_id'])
        pdf_text_preview = pdf_text[:800] if pdf_text else ""

    if request.method == 'POST':
        if 'pdf_file' in request.files:
            pdf_file = request.files['pdf_file']
            if pdf_file.filename.endswith('.pdf'):
                pdf_bytes = pdf_file.read()
                text = extract_text_from_pdf(BytesIO(pdf_bytes))
                if text:
                    file_id, _ = save_text_to_temp_file(text)
                    session['pdf_file_id'] = file_id
                    flash('Fichier PDF chargé avec succès !', 'success')
                else:
                    flash('Aucun texte extrait du PDF.', 'warning')
            else:
                flash('Veuillez charger un fichier PDF.', 'error')
            return redirect(url_for('index'))

    return render_template('revision.html', subject=subject, day=day, hour=hour, pdf_text=pdf_text_preview)


@app.route('/generate_quiz', methods=['POST'])
def generate_quiz():
    if 'pdf_file_id' not in session:
        flash('Veuillez d’abord charger un fichier PDF.', 'error')
        return redirect(url_for('revision'))

    pdf_text = read_text_from_temp_file(session['pdf_file_id'])
    if not pdf_text:
        flash('Erreur : Contenu du PDF non disponible.', 'error')
        return redirect(url_for('revision'))

    quiz_text = generate_quiz_from_text(pdf_text)
    if quiz_text:
        session['quiz_raw'] = quiz_text
        session['user_answers'] = {}
        session['quiz_done'] = False
        flash('Quiz généré avec succès !', 'success')
    else:
        flash('Erreur lors de la génération du quiz.', 'error')
    return redirect(url_for('quiz'))

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if not session.get('quiz_raw'):
        flash('Aucun quiz disponible. Veuillez générer un quiz.', 'error')
        return redirect(url_for('index'))

    print("Quiz raw content:", session['quiz_raw'])  # Debug: Print quiz_raw
    lines = session['quiz_raw'].strip().split('\n')
    current_question = {}
    questions = []

    for line in lines:
        line = line.strip()
        if not line:
            continue  # Skip empty lines
        print("Processing line:", line)  # Debug: Print each line
        if line.startswith(("1.", "2.", "3.", "4.", "5.")):
            if current_question:
                questions.append(current_question)
            current_question = {"question": line, "options": []}
        elif line.startswith(("A)", "B)", "C)", "D)")) and current_question:
            option = line
            is_correct = "✅" in option
            option_clean = option.replace("✅", "").strip()
            current_question["options"].append((option_clean, is_correct))
        else:
            print(f"Skipping invalid line: {line}")  # Debug: Log invalid lines

    if current_question and current_question.get("options"):
        questions.append(current_question)

    if not questions:
        flash('Erreur : Aucun quiz valide généré. Veuillez réessayer.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        score = 0
        incorrect_questions = []
        for i, q in enumerate(questions):
            user_answer = request.form.get(f'q{i}')
            correct_answer = next((opt[0] for opt in q["options"] if opt[1]), None)
            if user_answer and correct_answer:  # Ensure both are valid
                session['user_answers'][f'q{i}'] = (user_answer, correct_answer)
                if user_answer == correct_answer:
                    score += 1
                else:
                    incorrect_questions.append({
                        "question": q["question"],
                        "user_answer": user_answer,
                        "correct_answer": correct_answer,
                        "options": q["options"]
                    })
            else:
                print(f"Warning: Invalid answer for q{i}: user_answer={user_answer}, correct_answer={correct_answer}")

        session['score'] = score
        session['incorrect_questions'] = incorrect_questions
        session['quiz_done'] = True
        flash(f'Ton score est : {score} / {len(questions)}', 'success')
        return redirect(url_for('results'))

    return render_template('quiz.html', questions=questions)

@app.route('/results')
def results():
    print("Template search path:", app.jinja_loader.searchpath)  # Debug: Print template search path
    print("Templates directory contents:", os.listdir('templates'))  # Debug: List templates
    print("User answers:", session.get('user_answers', {}))  # Debug: Print user_answers
    if not session.get('quiz_done'):
        flash('Veuillez d’abord soumettre le quiz.', 'error')
        return redirect(url_for('quiz'))

    questions = []
    lines = session['quiz_raw'].strip().split('\n')
    current_question = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue  # Skip empty lines
        if line.startswith(("1.", "2.", "3.", "4.", "5.")):
            if current_question:
                questions.append(current_question)
            current_question = {"question": line, "options": []}
        elif line.startswith(("A)", "B)", "C)", "D)")) and current_question:
            option = line
            is_correct = "✅" in option
            option_clean = option.replace("✅", "").strip()
            current_question["options"].append((option_clean, is_correct))

    if current_question and current_question.get("options"):
        questions.append(current_question)

    return render_template('results.html', questions=questions, user_answers=session['user_answers'], score=session['score'])

@app.route('/generate_summary', methods=['POST'])
def generate_summary():
    if not session.get('quiz_done'):
        flash('Veuillez d’abord soumettre le quiz.', 'error')
        return redirect(url_for('quiz'))

    if 'pdf_file_id' not in session:
        flash('Erreur : Contenu du PDF non disponible.', 'error')
        return redirect(url_for('index'))

    pdf_text = read_text_from_temp_file(session['pdf_file_id'])
    if not pdf_text:
        flash('Erreur : Contenu du PDF non disponible.', 'error')
        return redirect(url_for('index'))

    incorrect_parts_text = "\n".join([
        f"- {q['question']}\n  ✅ Bonne réponse : {q['correct_answer']}" for q in session['incorrect_questions']
    ])

    prompt = f"""
Tu es un assistant pédagogique. Lis le cours suivant, extrait d’un fichier PDF :

{pdf_text}

1. Génère un **résumé de cours un peu détaillé** pédagogique et structuré de ce cours pour un étudiant.
2. À la fin du résumé, ajoute une section intitulée : "⚠️ Erreurs à retravailler", où tu listes brièvement les points où l'étudiant s’est trompé pendant le quiz. Ne développe pas trop ces points, indique juste ce qu’il faut revoir.

Voici les erreurs faites pendant le quiz :
{incorrect_parts_text}
"""

    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3.2:latest",
            "prompt": prompt,
            "stream": False
        })
        response.raise_for_status()
        resume = response.json().get("response", "")
        session['resume'] = resume
        flash('Résumé généré avec succès !', 'success')
    except Exception:
        flash('Erreur lors de la génération du résumé.', 'error')
    return redirect(url_for('summary'))

@app.route('/summary')
def summary():
    if 'resume' not in session:
        flash('Aucun résumé disponible. Veuillez générer un résumé.', 'error')
        return redirect(url_for('results'))
    return render_template('summary.html', resume=session['resume'])

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'pdf_file_id' not in session:
        flash('Veuillez d’abord charger un fichier PDF.', 'error')
        return redirect(url_for('index'))

    pdf_text = read_text_from_temp_file(session['pdf_file_id'])
    if not pdf_text:
        flash('Erreur : Contenu du PDF non disponible.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        user_input = request.form.get('user_input')
        if user_input:
            chat_history_text = "\n".join([
                f"Étudiant : {pair['user']}\nAssistant : {pair['assistant']}" for pair in session['chat_history']
            ])

            prompt_chat = f"""
Voici le contenu d’un cours :

{pdf_text}

Historique de conversation :
{chat_history_text}

Nouvelle comentario de l’étudiant :
{user_input}

Réponds de manière claire et pédagogique, en t’appuyant uniquement sur le contenu du cours.
"""

            try:
                response = requests.post("http://localhost:11434/api/generate", json={
                    "model": "llama3.2:latest",
                    "prompt": prompt_chat,
                    "stream": False
                })
                response.raise_for_status()
                reply = response.json().get("response", "")
                session['chat_history'].append({
                    "user": user_input,
                    "assistant": reply
                })
                session.modified = True
            except Exception:
                flash('Erreur lors de la réponse du chatbot.', 'error')
        return redirect(url_for('chat'))

    return render_template('chat.html', chat_history=session['chat_history'])

@app.route('/clear_session', methods=['POST'])
def clear_session():
    if 'pdf_file_id' in session:
        delete_temp_file(session['pdf_file_id'])
    session.clear()
    flash('Session réinitialisée avec succès.', 'success')
    return redirect(url_for('index'))


# Run the app
if __name__ == "__main__":
    app.run(debug=True)