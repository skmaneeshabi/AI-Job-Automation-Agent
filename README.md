# AI Job Automation Agent

A Flask-based AI Job Automation Agent for managing candidates, jobs, resume generation, job matching, applications, interview scheduling, recruiter communication, and job-search analytics.

## Features

### Candidate Management
- Add, edit, view, search, and delete candidates
- Candidate education, skills, experience, projects, location, and target role
- Resume upload support: PDF, DOC, DOCX, TXT, and RTF
- AI-generated resume option
- Find suitable jobs for a candidate

### Job Management
- Add, edit, view, analyze, and delete jobs
- Job title, company, location, salary, description, and required skills
- Skill extraction from job descriptions
- Candidate-job matching with match percentage
- Matched and missing skills display

### Application Automation
- Create applications for candidates and jobs
- Automatic generation of:
  - Customized resume content
  - Cover letter
  - Interview/application answers
  - Recruiter email
- Application status tracking:
  - Saved
  - Applied
  - Shortlisted
  - Interview
  - Rejected
  - Selected
- Application view/edit/delete management

### Interview Scheduling
- Manual interview scheduling
- Automatic interview scheduling
- Browser-based reminders for upcoming interviews
- Reminder intervals include 1 day, 1 hour, and 5 minutes before the interview
- Browser must remain open for client-side reminder alerts

### Dashboard & Analytics
- Candidate count
- Job count
- Application count
- Interview count
- Selected count
- Application pipeline and job-search analytics

### Company Check
- Basic company information/check workflow for job listings

### UI
- Responsive Flask web interface
- Candidate action buttons for View, Edit, and Delete
- Job action buttons for View, Edit, Analyze, and Delete
- Application tracker actions
- Responsive two-column job cards on larger screens
- Mobile-friendly layout

## Technology Stack

- Python
- Flask
- SQLite
- HTML/CSS
- Vanilla JavaScript
- No external AI API key required

## Run Locally

1. Extract the ZIP file.
2. Open the project folder in VS Code.
3. Open a terminal in the project folder.
4. Create a virtual environment (recommended):

```bash
python -m venv venv
```

5. Activate it on Windows:

```bash
venv\Scripts\activate
```

6. Install dependencies:

```bash
pip install -r requirements.txt
```

7. Run the application:

```bash
python app.py
```

8. Open:

```text
http://127.0.0.1:5000
```

The SQLite database is created automatically when the application starts.

## Project Structure

```text
AI-Job-Automation-Agent/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── uploads/
    └── .gitkeep
```

## GitHub

Upload the project files to your GitHub repository. Do not upload generated SQLite databases, Python cache files, virtual environments, or private uploaded resumes.

## Note

This project currently uses offline/template-based generation logic and does not require an API key. It is designed as a practical portfolio project for candidate and job application automation.
