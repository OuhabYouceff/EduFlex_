```
Timetable Parser (image) ──────┐
                               │
                               ▼
                        Google Calendar  ←───── Sync availability
                               │
                               ▼
      +-----------------+  structured slots   +-------------------+
      | Curriculum JSON | ────────────────────▶ | Planning Agent     |
      +-----------------+                    +-------------------+
                                                    │
                                                    ▼
                                        +-------------------------+
                                        | Google Calendar API     | ←── export events
                                        +-------------------------+
```

# EduFlex\_

**EduFlex\_** is a Python-based scheduling assistant designed to streamline academic planning by integrating curriculum data with Google Calendar. It automates the process of generating and managing study sessions, ensuring an organized and efficient learning experience.

---

## Features

* **Curriculum Integration**: Parses structured curriculum data from `curriculum.json` to identify courses, topics, and schedules.
* **Timetable Parsing**: Processes timetable information from `calendrier.json` to determine available time slots.
* **Google Calendar Synchronization**: Utilizes the Google Calendar API to create and manage events based on the planned study sessions.
* **Session Management**: Stores and handles session data through `sessions.json` for tracking and updates.

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/OuhabYouceff/EduFlex_.git
cd EduFlex_
```

### Create a Virtual Environment (optional but recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Set Up Google Calendar API Credentials

* Obtain your `credentials.json` from the [Google Cloud Console](https://console.cloud.google.com/).
* Place the `credentials.json` file in the root directory of the project.

---

## Usage

### Prepare Your Data

* Ensure `curriculum.json` contains your course and topic information.
* Ensure `calendrier.json` contains your timetable or availability data.

### Run the Application

```bash
python app.py
```

The application will process the curriculum and timetable data, then synchronize the planned sessions with your Google Calendar.

---

## Project Structure

```plaintext
EduFlex_/
├── app.py                 # Main application script
├── curriculum.json        # Curriculum data
├── calendrier.json        # Timetable data
├── sessions.json          # Session tracking data
├── requirements.txt       # Python dependencies
├── routes/                # Flask route handlers
├── static/                # Static files (CSS, JS, images)
├── templates/             # HTML templates for rendering
├── utils/                 # Utility functions and modules
└── .env                   # Environment variables (e.g., API keys)
```

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Contact

For questions or suggestions, feel free to reach out to **MindFusion** via [mindfusion@gmail.com](mailto:mindfusion@gmail.com).
