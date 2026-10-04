from flask import Flask, request, redirect, url_for, render_template_string, send_from_directory
import sqlite3
from datetime import datetime, timedelta
import os
import re

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_RESUME_EXTENSIONS = {"pdf", "doc", "docx", "txt", "rtf"}

# New database so it doesn't conflict with the previous version
DB = "job_agent_v2.db"


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = db()
    cur = conn.cursor()

    # -------------------------
    # CANDIDATES
    # -------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            education TEXT,
            skills TEXT,
            experience TEXT,
            projects TEXT,
            location TEXT,
            target_role TEXT,
            resume TEXT,
            created_at TEXT,
            resume_file TEXT
        )
    """)

    # -------------------------
    # JOBS
    # -------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            salary TEXT,
            description TEXT,
            required_skills TEXT,
            created_at TEXT
        )
    """)

    # -------------------------
    # APPLICATIONS
    # -------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            job_id INTEGER,
            match_score INTEGER,
            matched_skills TEXT,
            missing_skills TEXT,
            resume TEXT,
            cover_letter TEXT,
            answers TEXT,
            recruiter_email TEXT,
            status TEXT,
            interview_date TEXT,
            created_at TEXT,

            FOREIGN KEY(candidate_id)
            REFERENCES candidates(id),

            FOREIGN KEY(job_id)
            REFERENCES jobs(id)
        )
    """)

    # Safe migrations for the enhanced version.
    existing_candidates = {row[1] for row in conn.execute("PRAGMA table_info(candidates)").fetchall()}
    if "resume_file" not in existing_candidates:
        conn.execute("ALTER TABLE candidates ADD COLUMN resume_file TEXT")

    existing_apps = {row[1] for row in conn.execute("PRAGMA table_info(applications)").fetchall()}
    if "interview_date" not in existing_apps:
        conn.execute("ALTER TABLE applications ADD COLUMN interview_date TEXT")

    conn.commit()
    conn.close()


init_db()


# =========================================================
# SKILL DATABASE
# =========================================================

SKILLS = [
    "python",
    "java",
    "c",
    "c++",
    "javascript",
    "typescript",
    "html",
    "css",
    "react",
    "node",
    "express",
    "mongodb",
    "sql",
    "mysql",
    "postgresql",
    "git",
    "github",
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "ai",
    "generative ai",
    "genai",
    "prompt engineering",
    "data analytics",
    "data analysis",
    "pandas",
    "numpy",
    "power bi",
    "tableau",
    "tensorflow",
    "pytorch",
    "flask",
    "django",
    "aws",
    "azure",
    "docker",
    "rest api",
    "api",
    "data structures",
    "algorithms",
    "communication",
    "problem solving",
    "excel",
    "leadership",
    "teamwork"
]


def extract_skills(text):

    text = (text or "").lower()

    found = []

    for skill in SKILLS:

        pattern = r"(?<!\w)" + re.escape(skill) + r"(?!\w)"
        if re.search(pattern, text):
            found.append(skill)

    return sorted(set(found))


def calculate_match(candidate, job):

    candidate_text = " ".join([
        candidate["skills"] or "",
        candidate["education"] or "",
        candidate["experience"] or "",
        candidate["projects"] or "",
        candidate["resume"] or ""
    ])

    job_text = " ".join([
        job["description"] or "",
        job["required_skills"] or ""
    ])

    candidate_skills = set(
        extract_skills(candidate_text)
    )

    # If the recruiter entered Required Skills, use those skills
    # for matching. Otherwise detect skills from the job description.
    explicit_required = {
        skill.strip().lower()
        for skill in re.split(r"[,;\n]+", job["required_skills"] or "")
        if skill.strip()
    }

    if explicit_required:
        job_skills = explicit_required
    else:
        job_skills = set(extract_skills(job_text))

    if not job_skills:

        return 0, [], []

    matched = sorted(
        candidate_skills.intersection(job_skills)
    )

    missing = sorted(
        job_skills - candidate_skills
    )

    score = int(
        len(matched) / len(job_skills) * 100
    )

    return score, matched, missing


def company_check(company):
    """Basic offline warning system; it does NOT verify a company online."""
    suspicious = [
        "registration fee", "processing fee", "pay money",
        "pay fee", "deposit money", "guaranteed job"
    ]
    text = (company or "").lower()
    if len(text.strip()) < 3:
        return "❌ Invalid company name"
    if any(word in text for word in suspicious):
        return "⚠️ Potentially suspicious"
    return "✅ Name looks valid"


def next_business_day(days=2):
    date = datetime.now()
    added = 0
    while added < days:
        date += timedelta(days=1)
        if date.weekday() < 5:
            added += 1
    return date.replace(hour=10, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")


# =========================================================
# GENERATORS
# =========================================================

def make_candidate_resume(candidate):
    """Generate a professional resume directly from candidate details.
    This works offline and does not require an API key.
    """
    return f"""{candidate['name']}

Email: {candidate['email']}
Phone: {candidate['phone']}
Location: {candidate['location']}

PROFESSIONAL SUMMARY
Motivated candidate seeking opportunities as a {candidate['target_role'] or 'Software Professional'}.
Strong interest in technology with hands-on academic projects and a willingness to learn.

EDUCATION
{candidate['education'] or 'Not provided'}

TECHNICAL SKILLS
{candidate['skills'] or 'Not provided'}

EXPERIENCE
{candidate['experience'] or 'Fresher / Not provided'}

PROJECTS
{candidate['projects'] or 'Not provided'}

TARGET ROLE
{candidate['target_role'] or 'Not specified'}
""".strip()


def make_resume(candidate, job, matched):

    skills = ", ".join(matched)

    return f"""
{candidate['name']}

Email: {candidate['email']}
Phone: {candidate['phone']}
Location: {candidate['location']}

TARGET POSITION
{job['title']} - {job['company']}

PROFESSIONAL SUMMARY
Motivated candidate seeking the {job['title']} position.
Academic background, technical skills and project experience
are aligned with the requirements of this opportunity.

EDUCATION
{candidate['education']}

TECHNICAL SKILLS
{candidate['skills']}

JOB-MATCHED SKILLS
{skills}

EXPERIENCE
{candidate['experience']}

PROJECTS
{candidate['projects']}
""".strip()


def make_cover_letter(candidate, job, matched):

    skills = ", ".join(matched)

    return f"""
Dear Hiring Manager,

I am writing to apply for the {job['title']} position
at {job['company']}.

My background includes {candidate['education']} and experience
with {skills if skills else candidate['skills']}.

I am interested in this opportunity because it aligns with
my technical interests and career goals. I am eager to apply
my knowledge to real-world problems and continue developing
my skills.

Thank you for considering my application.

Regards,
{candidate['name']}
{candidate['email']}
""".strip()


def make_answers(candidate, job):

    return f"""
1. Why are you interested in this position?

I am interested in the {job['title']} position because it
matches my technical background, projects and career goals.

2. Why should we consider you?

I have a background in {candidate['education']} and experience
with {candidate['skills']}. I am a motivated learner and enjoy
solving practical technical problems.

3. What are your relevant technical skills?

{candidate['skills']}

4. Tell us about your experience.

{candidate['experience']}

5. Tell us about a relevant project.

{candidate['projects']}
""".strip()


def make_email(candidate, job, matched):

    skills = ", ".join(matched)

    return f"""
Subject: Application for {job['title']} - {candidate['name']}

Dear Hiring Manager,

I am interested in the {job['title']} opportunity at
{job['company']}.

My relevant skills include:
{skills if skills else candidate['skills']}

I would appreciate the opportunity to be considered for this role.

Thank you for your time.

Regards,
{candidate['name']}
{candidate['email']}
""".strip()


# =========================================================
# COMMON HTML
# =========================================================

PAGE = """
<!DOCTYPE html>

<html>

<head>

<title>Job Automation Agent</title>

<meta name="viewport"
content="width=device-width, initial-scale=1">

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f3f4f6;
    color: #1f2937;
}

/* NAVBAR */

.navbar {
    background: #111827;
    color: white;
    padding: 16px 28px;

    display: flex;
    justify-content: space-between;
    align-items: center;

    position: sticky;
    top: 0;
    z-index: 10;
}

.logo {
    font-size: 21px;
    font-weight: bold;
}

.nav a {
    color: white;
    text-decoration: none;
    margin-left: 18px;
    font-size: 14px;
}

.nav a:hover {
    color: #93c5fd;
}

/* CONTAINER */

.container {
    width: 94%;
    max-width: 1250px;
    margin: 28px auto;
}

/* CARDS */

.card {
    background: white;
    padding: 24px;
    border-radius: 12px;
    margin-bottom: 22px;

    box-shadow:
        0 2px 8px rgba(0,0,0,0.06);
}

/* DASHBOARD */

.stats {
    display: grid;
    grid-template-columns:
        repeat(4, 1fr);

    gap: 18px;
    margin: 20px 0;
}

.stat {
    background: white;
    padding: 25px;
    border-radius: 12px;
    text-align: center;
}

.stat h2 {
    font-size: 32px;
    margin: 5px;
    color: #2563eb;
}

/* FORMS */

label {
    display: block;
    font-weight: bold;
    margin-top: 12px;
}

input,
textarea,
select {

    width: 100%;

    padding: 12px;

    border: 1px solid #d1d5db;

    border-radius: 7px;

    margin-top: 6px;
    margin-bottom: 12px;

    font-size: 14px;
}

textarea {
    min-height: 120px;
    resize: vertical;
}

/* BUTTONS */

button,
.button {

    display: inline-block;

    background: #2563eb;

    color: white;

    border: none;

    padding: 11px 18px;

    border-radius: 7px;

    cursor: pointer;

    text-decoration: none;

    font-size: 14px;
}

button:hover,
.button:hover {
    background: #1d4ed8;
}

.danger {
    background: #dc2626;
}

.danger:hover {
    background: #b91c1c;
}

.secondary {
    background: #6b7280;
}

.green {
    background: #16a34a;
}

/* TABLE */

.table-wrap {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th,
td {
    padding: 13px;

    border-bottom:
        1px solid #e5e7eb;

    text-align: left;
}

th {
    background: #f9fafb;
}

/* TAGS */

.tag {
    display: inline-block;

    padding: 6px 10px;

    margin: 3px;

    border-radius: 20px;

    background: #dbeafe;

    font-size: 12px;
}

.missing {
    background: #fee2e2;
}

.success {
    background: #dcfce7;

    padding: 13px;

    border-radius: 7px;

    margin-bottom: 15px;
}

.warning {
    background: #fef3c7;

    padding: 13px;

    border-radius: 7px;

    margin-bottom: 15px;
}

/* JOB CARD */

.job-card {
    border: 1px solid #e5e7eb;

    border-radius: 10px;

    padding: 18px;

    margin-bottom: 15px;

    background: #fff;
}

/* CANDIDATE ACTIONS - horizontal and attractive */

.action-stack {
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 8px;
    align-items: center;
    white-space: nowrap;
}

.action-stack .button {
    width: auto;
    min-width: 88px;
    text-align: center;
    margin: 0;
    padding: 9px 13px;
    font-weight: 600;
}

.action-stack .view-button {
    background: #2563eb;
    color: #ffffff;
}

.resume-action .view-button {
    display: inline-block;
    width: 88px;
    min-width: 88px;
    padding: 9px 13px;
    text-align: center;
    font-weight: 600;
    margin: 0;
    background: #2563eb;
    color: #ffffff;
}

.resume-action .view-button:hover {
    background: #1d4ed8;
}

.no-resume {
    color: #6b7280;
    font-size: 14px;
}

.action-stack .view-button:hover {
    background: #1d4ed8;
}

.action-stack .edit-button {
    background: #7c3aed;
    color: #ffffff;
}

.action-stack .edit-button:hover {
    background: #6d28d9;
}

.action-stack .delete-button {
    background: #dc2626;
    color: #ffffff;
}

.action-stack .delete-button:hover {
    background: #b91c1c;
}

/* JOB GRID - use the empty right side */

.job-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
}

.job-grid .job-card {
    margin-bottom: 0;
    height: 100%;
}

.job-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 15px;
}

.job-actions .button { min-width: 82px; text-align: center; font-weight: 600; }
.view-button { background: #2563eb; }
.view-button:hover { background: #1d4ed8; }
.analyze-button { background: #0891b2; }
.analyze-button:hover { background: #0e7490; }
.edit-button { background: #7c3aed; }
.edit-button:hover { background: #6d28d9; }
.delete-button { background: #dc2626; }
.delete-button:hover { background: #b91c1c; }

@media(max-width: 850px) {
    .job-grid {
        grid-template-columns: 1fr;
    }
}

/* SCORE */

.score {
    font-size: 25px;
    font-weight: bold;
    color: #2563eb;
}

/* TEXT */

pre {
    background: #f8fafc;

    padding: 20px;

    border-radius: 8px;

    white-space: pre-wrap;

    line-height: 1.6;
}

/* TWO COLUMNS */

.two-col {

    display: grid;

    grid-template-columns:
        1fr 1fr;

    gap: 22px;
}

/* STATUS */

.status {
    padding: 6px 10px;

    border-radius: 20px;

    background: #e0e7ff;

    font-size: 12px;
}

/* MOBILE */

@media(max-width: 850px) {

    .navbar {
        flex-direction: column;
        gap: 15px;
    }

    .stats {
        grid-template-columns: 1fr 1fr;
    }

    .two-col {
        grid-template-columns: 1fr;
    }

    .nav a {
        margin-left: 8px;
    }

}

</style>

</head>

<body>

<div class="navbar">

<div class="logo">
🤖 Job Automation Agent
</div>

<div class="nav">

<a href="/">Dashboard</a>

<a href="/candidates">Candidates</a>

<a href="/jobs">Jobs</a>

<a href="/applications">Applications</a>

<a href="/analytics">Analytics</a>

</div>

</div>

<div class="container">

{{ content | safe }}

</div>

<script>
function toggleJobForm() {
    const form = document.getElementById("jobForm");
    if (!form) return;

    if (form.style.display === "none" || form.style.display === "") {
        form.style.display = "block";
        form.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
        form.style.display = "none";
    }
}

function toggleCandidateForm() {
    const form = document.getElementById("candidateForm");
    if (!form) return;

    if (form.style.display === "none" || form.style.display === "") {
        form.style.display = "block";
        form.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
        form.style.display = "none";
    }
}

document.addEventListener("keydown", function(event) {
    if (event.key === "Enter" && event.target.tagName !== "TEXTAREA") {
        const form = event.target.closest("form");
        if (form && event.target.tagName !== "BUTTON") {
            event.preventDefault();
        }
    }
});
</script>

</body>

</html>
"""


def render_page(content):

    return render_template_string(
        PAGE,
        content=content
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
def dashboard():

    conn = db()

    candidates = conn.execute(
        "SELECT COUNT(*) FROM candidates"
    ).fetchone()[0]

    jobs = conn.execute(
        "SELECT COUNT(*) FROM jobs"
    ).fetchone()[0]

    applications = conn.execute(
        "SELECT COUNT(*) FROM applications"
    ).fetchone()[0]

    interviews = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status='Interview'"
    ).fetchone()[0]

    recent = conn.execute("""
        SELECT
            applications.*,
            candidates.name AS candidate_name,
            jobs.title AS job_title,
            jobs.company AS company
        FROM applications
        JOIN candidates
        ON applications.candidate_id = candidates.id
        JOIN jobs
        ON applications.job_id = jobs.id
        ORDER BY applications.id DESC
        LIMIT 8
    """).fetchall()

    conn.close()

    content = f"""

<h1>📊 Dashboard</h1>

<p>
Welcome to your Job Automation Agent.
</p>

<div class="stats">

<div class="stat">
<h2>{candidates}</h2>
<p>👥 Candidates</p>
</div>

<div class="stat">
<h2>{jobs}</h2>
<p>💼 Jobs</p>
</div>

<div class="stat">
<h2>{applications}</h2>
<p>📋 Applications</p>
</div>

<div class="stat">
<h2>{interviews}</h2>
<p>🎯 Interviews</p>
</div>

</div>

<div class="card">

<h2>⚡ Quick Actions</h2>

<a class="button" href="/candidates">
➕ Add Candidate
</a>

<a class="button" href="/jobs">
➕ Add Job
</a>

<a class="button" href="/applications">
📋 Create Application
</a>

</div>

<div class="card">

<h2>🕒 Recent Applications</h2>

"""

    if not recent:

        content += """
<p>No applications yet.</p>
"""

    else:

        content += """

<div class="table-wrap">

<table>

<tr>
<th>Candidate</th>
<th>Job</th>
<th>Company</th>
<th>Match</th>
<th>Status</th>
</tr>
"""

        for item in recent:

            content += f"""

<tr>

<td>
{item['candidate_name']}
</td>

<td>
{item['job_title']}
</td>

<td>
{item['company']}
</td>

<td>
{item['match_score']}%
</td>

<td>
<span class="status">
{item['status']}
</span>
</td>

</tr>

"""

        content += """
</table>
</div>
"""

    content += "</div>"

    return render_page(content)


# =========================================================
# CANDIDATES
# =========================================================

@app.route("/candidates", methods=["GET", "POST"])
def candidates():

    conn = db()

    # -------------------------
    # SAVE NEW CANDIDATE
    # -------------------------

    if request.method == "POST":

        resume_file = request.files.get("resume_file")
        resume_filename = ""

        if resume_file and resume_file.filename:
            extension = resume_file.filename.rsplit(".", 1)[-1].lower() if "." in resume_file.filename else ""

            if extension not in ALLOWED_RESUME_EXTENSIONS:
                conn.close()
                return "Unsupported resume format. Please upload PDF, DOC, DOCX, TXT or RTF."

            safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", resume_file.filename)
            unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
            resume_file.save(os.path.join(UPLOAD_FOLDER, unique_name))
            resume_filename = unique_name

        conn.execute("""
            INSERT INTO candidates
            (
                name,
                email,
                phone,
                education,
                skills,
                experience,
                projects,
                location,
                target_role,
                resume,
                created_at,
                resume_file
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            request.form.get("name"),

            request.form.get("email"),

            request.form.get("phone"),

            request.form.get("education"),

            request.form.get("skills"),

            request.form.get("experience"),

            request.form.get("projects"),

            request.form.get("location"),

            request.form.get("target_role"),

            resume_filename,

            datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            ),

            resume_filename

        ))

        conn.commit()

        conn.close()

        return redirect(
            url_for(
                "candidates",
                saved="1"
            )
        )

    # -------------------------
    # GET CANDIDATES
    # -------------------------

    search = request.args.get(
        "search",
        ""
    )

    if search:

        candidates_list = conn.execute("""
            SELECT *
            FROM candidates
            WHERE name LIKE ?
            OR email LIKE ?
            OR target_role LIKE ?
            ORDER BY id DESC
        """, (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        )).fetchall()

    else:

        candidates_list = conn.execute("""
            SELECT *
            FROM candidates
            ORDER BY id DESC
        """).fetchall()

    conn.close()

    saved = request.args.get("saved")

    content = """

<h1>👥 Candidate Management</h1>

<div style="margin:15px 0 20px;">

<button type="button" class="button" onclick="toggleCandidateForm()">
➕ Add Candidate
</button>

</div>
"""

    if saved:

        content += """

<div class="success">
✅ Candidate saved successfully!
You can add another candidate below.
</div>

"""

    # -------------------------
    # CANDIDATE LIST
    # -------------------------

    content += """

<div class="card">

<h2>📋 Candidate List</h2>

<form method="GET">

<input
name="search"
placeholder="Search candidate by name, email or role..."
>

<button type="submit">
🔎 Search
</button>

<a
class="button secondary"
href="/candidates"
>
Clear
</a>

</form>

"""

    if not candidates_list:

        content += """
<p>No candidates found.</p>
"""

    else:

        content += """

<div class="table-wrap">

<table>

<tr>

<th>ID</th>
<th>Name</th>
<th>Email</th>
<th>Target Role</th>
<th>Location</th>
<th>Resume</th>
<th>Actions</th>

</tr>
"""

        for c in candidates_list:

            content += f"""

<tr>

<td>{c['id']}</td>

<td>
<b>{c['name']}</b>
</td>

<td>
{c['email']}
</td>

<td>
{c['target_role']}
</td>

<td>
{c['location']}
</td>

<td>

<div class="resume-action">
{(f'<a class="button view-button" href="/uploads/{c["resume"]}" target="_blank" title="View resume">👁️ View</a>' if c['resume'] else '<span class="no-resume">No resume</span>')}
</div>

</td>

<td>

<div class="action-stack">

<a
class="button edit-button"
href="/candidate/{c['id']}/edit"
title="Edit candidate"
>
✏️ Edit
</a>

<a
class="button delete-button"
href="/candidate/{c['id']}/delete"
onclick="return confirm('Delete this candidate?')"
title="Delete candidate"
>
🗑️ Delete
</a>

</div>

</td>

</tr>

"""

        content += """
</table>
</div>
"""

    content += """

</div>

"""

    # -------------------------
    # NEW CANDIDATE FORM
    # -------------------------

    content += """

<div id="candidateForm" class="card" style="display:none; margin-top:20px;">

<h2>➕ Add New Candidate</h2>

<p>
Fill this form and click Save. After saving,
the candidate will appear in the list.
</p>

<form method="POST" enctype="multipart/form-data" onkeydown="if(event.key==='Enter' && event.target.tagName!=='TEXTAREA') event.preventDefault();">

<label>Name *</label>

<input
name="name"
placeholder="Candidate full name"
required
>

<label>Email</label>

<input
type="email"
name="email"
placeholder="candidate@email.com"
>

<label>Phone</label>

<input
name="phone"
placeholder="+91 XXXXX XXXXX"
>

<label>Education</label>

<input
name="education"
placeholder="B.Tech Computer Science"
>

<label>Skills</label>

<textarea
name="skills"
placeholder="Python, SQL, Generative AI, Prompt Engineering..."
></textarea>

<label>Experience</label>

<textarea
name="experience"
placeholder="Fresher / Internship / Work experience..."
></textarea>

<label>Projects</label>

<textarea
name="projects"
placeholder="Describe projects..."
></textarea>

<label>Location</label>

<input
name="location"
placeholder="Hyderabad"
>

<label>Target Job Role</label>

<input
name="target_role"
placeholder="Generative AI Developer"
>

<label>Resume File</label>

<input
type="file"
name="resume_file"
accept=".pdf,.doc,.docx,.txt,.rtf"
>
<small>Supported: PDF, DOC, DOCX, TXT and RTF.</small>

<button type="submit">
💾 Save Candidate
</button>

</form>

<button type="button" class="button secondary" onclick="toggleCandidateForm()">
Cancel
</button>

</div>

<script>
function toggleJobForm() {

    const form = document.getElementById("jobForm");

    if (form.style.display === "none" || form.style.display === "") {
        form.style.display = "block";
        window.scrollTo({ top: form.offsetTop - 20, behavior: "smooth" });
    } else {
        form.style.display = "none";
    }
}

function toggleCandidateForm() {
    const form = document.getElementById("candidateForm");
    if (form.style.display === "none") {
        form.style.display = "block";
        form.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
        form.style.display = "none";
    }
}
</script>

"""

    return render_page(content)


# =========================================================
# VIEW CANDIDATE
# =========================================================

@app.route("/candidate/<int:candidate_id>")
def view_candidate(candidate_id):

    conn = db()

    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id=?",
        (candidate_id,)
    ).fetchone()

    applications = conn.execute("""
        SELECT
            applications.*,
            jobs.title AS job_title,
            jobs.company AS job_company
        FROM applications
        JOIN jobs
        ON applications.job_id = jobs.id
        WHERE applications.candidate_id=?
        ORDER BY applications.id DESC
    """, (candidate_id,)).fetchall()

    conn.close()

    if not candidate:

        return "Candidate not found."

    content = f"""

<h1>👤 Candidate Profile</h1>

<div class="card">

<h2>{candidate['name']}</h2>

<p>
<b>Email:</b> {candidate['email']}
</p>

<p>
<b>Phone:</b> {candidate['phone']}
</p>

<p>
<b>Education:</b> {candidate['education']}
</p>

<p>
<b>Location:</b> {candidate['location']}
</p>

<p>
<b>Target Role:</b> {candidate['target_role']}
</p>

<h3>Skills</h3>

<p>
{candidate['skills']}
</p>

<h3>Experience</h3>

<pre>{candidate['experience']}</pre>

<h3>Projects</h3>

<pre>{candidate['projects']}</pre>

<h3>Resume</h3>

<p>{candidate['resume'] or 'No resume uploaded.'}</p>

{(f'<a class="button" href="/uploads/{candidate["resume"]}">📥 Download Resume</a>' if candidate['resume'] else '')}

<a
class="button"
href="/candidate/{candidate_id}/edit"
>
✏️ Edit Candidate
</a>

<a
class="button green"
href="/candidate/{candidate_id}/ai-resume"
>
🤖 AI Generated Resume
</a>

<a class="button" href="/candidate/{candidate_id}/suitable-jobs">🎯 Find Suitable Jobs</a>

<a
class="button secondary"
href="/candidates"
>
← Back
</a>

</div>

<div class="card">

<h2>📋 Application History</h2>

"""

    if not applications:

        content += """
<p>No applications for this candidate.</p>
"""

    else:

        content += """

<div class="table-wrap">

<table>

<tr>
<th>Job</th>
<th>Company</th>
<th>Match</th>
<th>Status</th>
<th>Action</th>
</tr>
"""

        for a in applications:

            content += f"""

<tr>

<td>{a['job_title']}</td>

<td>{a['job_company']}</td>

<td>{a['match_score']}%</td>

<td>
<span class="status">
{a['status']}
</span>
</td>

<td>
<a
class="button"
href="/application/{a['id']}"
>
View
</a>
</td>

</tr>

"""

        content += """
</table>
</div>
"""

    content += "</div>"

    return render_page(content)


# =========================================================
# FIND SUITABLE JOBS FOR CANDIDATE
# =========================================================

@app.route("/candidate/<int:candidate_id>/suitable-jobs")
def suitable_jobs(candidate_id):
    conn = db()
    candidate = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
    jobs_list = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    conn.close()
    if not candidate:
        return "Candidate not found.", 404
    ranked = []
    for job in jobs_list:
        score, matched, missing = calculate_match(candidate, job)
        ranked.append((score, job, matched, missing))
    ranked.sort(key=lambda x: x[0], reverse=True)
    content = f'''<h1>🎯 Suitable Jobs for {candidate['name']}</h1><div class="card"><p>Jobs are ranked by skill match using the candidate profile and each job's required skills.</p>'''
    if not ranked:
        content += '<p>No jobs available.</p>'
    else:
        content += '<div class="job-grid">'
        for score, job, matched, missing in ranked:
            content += f'''<div class="job-card"><h2>{job['title']}</h2><p><b>{job['company']}</b> · {job['location'] or 'Location not specified'}</p><p class="score">{score}% Match</p><p><b>Matched:</b> {', '.join(matched) or 'None'}</p><p><b>Missing:</b> {', '.join(missing) or 'None'}</p><div class="job-actions"><a class="button view-button" href="/job/{job['id']}">👁️ View Job</a><a class="button analyze-button" href="/job/{job['id']}/analyze">📊 Analyze</a></div></div>'''
        content += '</div>'
    content += f'<br><a class="button secondary" href="/candidate/{candidate_id}">← Back to Candidate</a></div>'
    return render_page(content)


# =========================================================
# EDIT CANDIDATE
# =========================================================

@app.route(
    "/candidate/<int:candidate_id>/edit",
    methods=["GET", "POST"]
)
def edit_candidate(candidate_id):

    conn = db()

    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id=?",
        (candidate_id,)
    ).fetchone()

    if not candidate:

        conn.close()

        return "Candidate not found."

    if request.method == "POST":

        resume_filename = candidate["resume_file"] or candidate["resume"] or ""
        resume_file = request.files.get("resume_file")

        if resume_file and resume_file.filename:
            extension = resume_file.filename.rsplit(".", 1)[-1].lower() if "." in resume_file.filename else ""

            if extension not in ALLOWED_RESUME_EXTENSIONS:
                conn.close()
                return "Unsupported resume format. Please upload PDF, DOC, DOCX, TXT or RTF."

            safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", resume_file.filename)
            unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
            resume_file.save(os.path.join(UPLOAD_FOLDER, unique_name))
            resume_filename = unique_name

        conn.execute("""
            UPDATE candidates

            SET
                name=?,
                email=?,
                phone=?,
                education=?,
                skills=?,
                experience=?,
                projects=?,
                location=?,
                target_role=?,
                resume=?,
                resume_file=?

            WHERE id=?
        """, (

            request.form.get("name"),

            request.form.get("email"),

            request.form.get("phone"),

            request.form.get("education"),

            request.form.get("skills"),

            request.form.get("experience"),

            request.form.get("projects"),

            request.form.get("location"),

            request.form.get("target_role"),

            resume_filename,

            resume_filename,

            candidate_id

        ))

        conn.commit()

        conn.close()

        return redirect(
            url_for(
                "view_candidate",
                candidate_id=candidate_id
            )
        )

    conn.close()

    content = f"""

<h1>✏️ Edit Candidate</h1>

<div class="card">

<form method="POST" enctype="multipart/form-data" onkeydown="if(event.key==='Enter' && event.target.tagName!=='TEXTAREA') event.preventDefault();">

<label>Name</label>

<input
name="name"
value="{candidate['name']}"
required
>

<label>Email</label>

<input
name="email"
value="{candidate['email']}"
>

<label>Phone</label>

<input
name="phone"
value="{candidate['phone']}"
>

<label>Education</label>

<input
name="education"
value="{candidate['education']}"
>

<label>Skills</label>

<textarea
name="skills"
>{candidate['skills']}</textarea>

<label>Experience</label>

<textarea
name="experience"
>{candidate['experience']}</textarea>

<label>Projects</label>

<textarea
name="projects"
>{candidate['projects']}</textarea>

<label>Location</label>

<input
name="location"
value="{candidate['location']}"
>

<label>Target Role</label>

<input
name="target_role"
value="{candidate['target_role']}"
>

<label>Replace Resume File</label>

<input
type="file"
name="resume_file"
accept=".pdf,.doc,.docx,.txt,.rtf"
>

<p>Current file: {candidate['resume_file'] or candidate['resume'] or 'None'}</p>

<button type="submit">
💾 Update Candidate
</button>

<a
class="button secondary"
href="/candidate/{candidate_id}"
>
Cancel
</a>

</form>

</div>

"""

    return render_page(content)


# =========================================================
# AI GENERATED RESUME
# =========================================================

@app.route("/candidate/<int:candidate_id>/ai-resume")
def ai_generated_resume(candidate_id):

    conn = db()
    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id=?",
        (candidate_id,)
    ).fetchone()
    conn.close()

    if not candidate:
        return "Candidate not found.", 404

    resume = make_candidate_resume(candidate)

    content = f"""
<h1>🤖 AI Generated Resume</h1>

<div class="card">

<h2>{candidate['name']}</h2>
<p><b>Target Role:</b> {candidate['target_role'] or 'Not specified'}</p>

<pre>{resume}</pre>

<button type="button" class="button" onclick="window.print()">🖨️ Print / Save as PDF</button>

<a class="button secondary" href="/candidate/{candidate_id}">← Back to Candidate</a>

</div>
"""

    return render_page(content)


# =========================================================
# DELETE CANDIDATE
# =========================================================

@app.route("/candidate/<int:candidate_id>/delete")
def delete_candidate(candidate_id):

    conn = db()

    # Delete applications first
    conn.execute(
        "DELETE FROM applications WHERE candidate_id=?",
        (candidate_id,)
    )

    conn.execute(
        "DELETE FROM candidates WHERE id=?",
        (candidate_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("candidates")
    )


# =========================================================
# JOBS
# =========================================================

@app.route("/jobs", methods=["GET", "POST"])
def jobs():

    conn = db()

    if request.method == "POST":

        title = request.form.get("title")
        company = request.form.get("company")
        location = request.form.get("location")
        salary = request.form.get("salary")
        description = request.form.get("description")
        required_skills = request.form.get("required_skills", "").strip()

        # Use the skills entered by the recruiter.
        # If the field is left empty, detect skills from the job description.
        if required_skills:
            required = required_skills
        else:
            detected = extract_skills(description)
            required = ", ".join(detected)

        conn.execute("""
            INSERT INTO jobs
            (
                title,
                company,
                location,
                salary,
                description,
                required_skills,
                created_at
            )

            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (

            title,
            company,
            location,
            salary,
            description,
            required,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            )

        ))

        conn.commit()

        conn.close()

        return redirect(
            url_for(
                "jobs",
                saved="1"
            )
        )

    job_list = conn.execute("""
        SELECT *
        FROM jobs
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    saved = request.args.get("saved")

    content = """

<h1>💼 Job Management</h1>

<div style="margin:15px 0 20px;">

<button type="button" class="button" onclick="toggleJobForm()">
➕ Add Job
</button>

</div>
"""

    if saved:

        content += """

<div class="success">
✅ Job saved successfully!
You can add another job below.
</div>

"""

    # -------------------------
    # JOB LIST
    # -------------------------

    content += """

<div class="card">

<h2>📋 Available Jobs</h2>

<div class="job-grid">

"""

    if not job_list:

        content += """
<p>No jobs added yet.</p>
"""

    for job in job_list:

        content += f"""

<div class="job-card">

<h2>{job['title']}</h2>

<p>
<b>Company:</b>
{job['company']}
</p>

<p>
<b>Location:</b>
{job['location']}
</p>

<p>
<b>Salary:</b>
{job['salary']}
</p>

<p>
<b>Required Skills:</b>
{job['required_skills'] or 'Not detected'}
</p>

<p>
<b>Company Check:</b>
{company_check(job['company'])}
</p>

<div class="job-actions">
<a class="button view-button" href="/job/{job['id']}" title="View job">👁️ View</a>
<a class="button edit-button" href="/job/{job['id']}/edit" title="Edit job">✏️ Edit</a>
<a class="button analyze-button" href="/job/{job['id']}/analyze" title="Analyze job">📊 Analyze</a>
<a class="button delete-button" href="/job/{job['id']}/delete" onclick="return confirm('Delete this job and its applications?')" title="Delete job">🗑️ Delete</a>
</div>

</div>

"""

    content += """

</div>

</div>

"""

    # -------------------------
    # ADD JOB
    # -------------------------

    content += """

<div id="jobForm" class="card" style="display:none;">

<h2>➕ Add New Job</h2>

<form method="POST">

<label>Job Title *</label>

<input
name="title"
placeholder="Generative AI Developer"
required
>

<label>Company *</label>

<input
name="company"
placeholder="ABC Technologies"
required
>

<label>Location</label>

<input
name="location"
placeholder="Hyderabad / Remote"
>

<label>Salary</label>

<input
name="salary"
placeholder="6 - 10 LPA"
>

<label>Required Skills *</label>

<input
name="required_skills"
placeholder="Python, Generative AI, Prompt Engineering, Flask, SQL, Git/GitHub"
required
>

<p style="font-size:13px;color:#6b7280;margin-top:-4px;">
Enter skills separated by commas. Example: Python, Flask, SQL, Git, Generative AI
</p>

<label>Job Description *</label>

<textarea
name="description"
style="min-height:250px"
placeholder="Paste complete job description..."
required
></textarea>

<button type="submit">
💾 Save Job
</button>

<button type="button" class="button secondary" onclick="toggleJobForm()">
Cancel
</button>

</form>

</div>

"""

    return render_page(content)


# =========================================================
# EDIT JOB
# =========================================================

@app.route("/job/<int:job_id>/edit", methods=["GET", "POST"])
def edit_job(job_id):
    conn = db()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        return "Job not found.", 404
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        location = request.form.get("location", "").strip()
        salary = request.form.get("salary", "").strip()
        description = request.form.get("description", "").strip()
        required_skills = request.form.get("required_skills", "").strip()
        if not required_skills:
            required_skills = ", ".join(extract_skills(description))
        conn.execute("""
            UPDATE jobs
            SET title=?, company=?, location=?, salary=?, description=?, required_skills=?
            WHERE id=?
        """, (title, company, location, salary, description, required_skills, job_id))
        conn.commit()
        conn.close()
        return redirect(url_for("view_job", job_id=job_id))
    conn.close()
    content = f"""
<h1>✏️ Edit Job</h1>
<div class="card">
<form method="POST">
<label>Job Title *</label>
<input name="title" value="{job['title'] or ''}" required>
<label>Company *</label>
<input name="company" value="{job['company'] or ''}" required>
<label>Location</label>
<input name="location" value="{job['location'] or ''}">
<label>Salary</label>
<input name="salary" value="{job['salary'] or ''}">
<label>Required Skills</label>
<textarea name="required_skills" placeholder="Python, Generative AI, Flask, SQL, Git">{job['required_skills'] or ''}</textarea>
<label>Job Description *</label>
<textarea name="description" required>{job['description'] or ''}</textarea>
<button type="submit">💾 Update Job</button>
<a class="button secondary" href="/job/{job_id}">Cancel</a>
</form>
</div>
"""
    return render_page(content)


# =========================================================
# VIEW / ANALYZE JOB
# =========================================================

@app.route("/job/<int:job_id>")
def view_job(job_id):
    conn = db()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    candidates_list = conn.execute("SELECT * FROM candidates ORDER BY name").fetchall()
    conn.close()
    if not job:
        return "Job not found.", 404
    required = [x.strip() for x in re.split(r"[,;\n]+", job["required_skills"] or "") if x.strip()]
    if not required:
        required = extract_skills(job["description"] or "")
    content = f"""
<h1>👁️ Job Details</h1>
<div class="card">
<h2>{job['title']}</h2>
<p><b>Company:</b> {job['company']}</p>
<p><b>Location:</b> {job['location'] or 'Not specified'}</p>
<p><b>Salary:</b> {job['salary'] or 'Not specified'}</p>
<p><b>Company Check:</b> {company_check(job['company'])}</p>
<h3>Required Skills</h3><p>
"""
    for skill in required:
        content += f'<span class="tag">{skill}</span>'
    if not required:
        content += '<span class="tag">Not specified</span>'
    content += f"""
</p>
<h3>Job Description</h3>
<pre>{job['description'] or 'No description provided.'}</pre>
<div class="job-actions">
<a class="button edit-button" href="/job/{job_id}/edit">✏️ Edit</a>
<a class="button analyze-button" href="/job/{job_id}/analyze">📊 Analyze</a>
<a class="button delete-button" href="/job/{job_id}/delete" onclick="return confirm('Delete this job and its applications?')">🗑️ Delete</a>
<a class="button secondary" href="/jobs">← Back</a>
</div>
</div>
<div class="card">
<h2>🤖 Matching Candidates</h2>
<p>Ranked by required-skill match.</p>
"""
    ranked = []
    for candidate in candidates_list:
        score, matched, missing = calculate_match(candidate, job)
        ranked.append((score, candidate, matched, missing))
    ranked.sort(key=lambda x: x[0], reverse=True)
    if not ranked:
        content += '<p>No candidates available.</p>'
    else:
        content += '<div class="table-wrap"><table><tr><th>Candidate</th><th>Target Role</th><th>Match</th><th>Matched Skills</th><th>Missing Skills</th><th>Action</th></tr>'
        for score, candidate, matched, missing in ranked:
            content += f'''<tr><td><b>{candidate['name']}</b></td><td>{candidate['target_role'] or 'Not specified'}</td><td><span class="score">{score}%</span></td><td>{', '.join(matched) or 'None'}</td><td>{', '.join(missing) or 'None'}</td><td><a class="button" href="/candidate/{candidate['id']}">View</a></td></tr>'''
        content += '</table></div>'
    content += '</div>'
    return render_page(content)


# =========================================================
# DEDICATED JOB ANALYSIS
# =========================================================

@app.route("/job/<int:job_id>/analyze")
def analyze_job_page(job_id):
    conn = db()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    candidates_list = conn.execute("SELECT * FROM candidates").fetchall()
    conn.close()
    if not job:
        return "Job not found.", 404
    required = {x.strip().lower() for x in re.split(r"[,;\n]+", job["required_skills"] or "") if x.strip()}
    if not required:
        required = set(extract_skills(job["description"] or ""))
    ranked = []
    for candidate in candidates_list:
        score, matched, missing = calculate_match(candidate, job)
        ranked.append((score, candidate, matched, missing))
    ranked.sort(key=lambda x: x[0], reverse=True)
    avg = round(sum(x[0] for x in ranked) / len(ranked), 1) if ranked else 0
    strong = sum(1 for x in ranked if x[0] >= 70)
    medium = sum(1 for x in ranked if 40 <= x[0] < 70)
    weak = sum(1 for x in ranked if x[0] < 40)
    difficulty = "Beginner" if len(required) <= 3 else ("Intermediate" if len(required) <= 6 else "Advanced")
    content = f"""
<h1>📊 Job Analysis</h1>
<div class="stats">
<div class="stat"><h2>{len(required)}</h2><p>Required Skills</p></div>
<div class="stat"><h2>{avg}%</h2><p>Average Match</p></div>
<div class="stat"><h2>{strong}</h2><p>Strong Candidates</p></div>
<div class="stat"><h2>{difficulty}</h2><p>Difficulty</p></div>
</div>
<div class="card">
<h2>{job['title']} — {job['company']}</h2>
<p><b>Candidate distribution:</b> {strong} strong · {medium} medium · {weak} low</p>
<h3>🎯 Key Skills</h3>
"""
    for skill in sorted(required):
        content += f'<span class="tag">{skill}</span>'
    content += """
<h3>💡 Interview Focus Areas</h3>
<p>Focus on the required technical skills, practical project experience, problem solving, communication and the candidate's missing skills.</p>
</div>
<div class="card">
<h2>🏆 Best Matching Candidates</h2>
"""
    if ranked:
        content += '<div class="table-wrap"><table><tr><th>Rank</th><th>Candidate</th><th>Match</th><th>Matched</th><th>Missing</th><th>Action</th></tr>'
        for i, (score, candidate, matched, missing) in enumerate(ranked, 1):
            content += f'''<tr><td>{i}</td><td><b>{candidate['name']}</b></td><td><span class="score">{score}%</span></td><td>{', '.join(matched) or 'None'}</td><td>{', '.join(missing) or 'None'}</td><td><a class="button" href="/candidate/{candidate['id']}">View</a></td></tr>'''
        content += '</table></div>'
    else:
        content += '<p>No candidates available yet.</p>'
    content += f'<br><a class="button secondary" href="/job/{job_id}">← Back to Job</a></div>'
    return render_page(content)


# =========================================================
# ANALYZE JOB MATCH
# =========================================================

@app.route("/analyze-job", methods=["POST"])
def analyze_job():

    candidate_id = request.form.get(
        "candidate_id"
    )

    job_id = request.form.get(
        "job_id"
    )

    conn = db()

    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id=?",
        (candidate_id,)
    ).fetchone()

    job = conn.execute(
        "SELECT * FROM jobs WHERE id=?",
        (job_id,)
    ).fetchone()

    conn.close()

    if not candidate or not job:

        return "Candidate or job not found."

    score, matched, missing = calculate_match(
        candidate,
        job
    )

    content = f"""

<h1>📊 Candidate Match Result</h1>

<div class="card">

<h2>
{candidate['name']}
→
{job['title']}
</h2>

<p>
<b>Company:</b>
{job['company']}
</p>

<p class="score">
Match Score: {score}%
</p>

<h3>✅ Matching Skills</h3>

"""

    if matched:

        for skill in matched:

            content += f"""
<span class="tag">
{skill}
</span>
"""

    else:

        content += "<p>No matching skills found.</p>"

    content += """

<h3>⚠️ Missing Skills</h3>

"""

    if missing:

        for skill in missing:

            content += f"""
<span class="tag missing">
{skill}
</span>
"""

    else:

        content += """
<p>No major missing skills detected.</p>
"""

    content += f"""

<br><br>

<form method="POST"
action="/create-application">

<input
type="hidden"
name="candidate_id"
value="{candidate_id}"
>

<input
type="hidden"
name="job_id"
value="{job_id}"
>

<button type="submit">
✨ Generate Application
</button>

</form>

</div>

"""

    return render_page(content)


# =========================================================
# DELETE JOB
# =========================================================

@app.route("/job/<int:job_id>/delete")
def delete_job(job_id):

    conn = db()

    conn.execute(
        "DELETE FROM applications WHERE job_id=?",
        (job_id,)
    )

    conn.execute(
        "DELETE FROM jobs WHERE id=?",
        (job_id,)
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("jobs")
    )


# =========================================================
# APPLICATIONS
# =========================================================

@app.route("/applications")
def applications():

    conn = db()

    applications_list = conn.execute("""
        SELECT
            applications.*,
            candidates.name AS candidate_name,
            jobs.title AS job_title,
            jobs.company AS job_company
        FROM applications

        JOIN candidates
        ON applications.candidate_id =
           candidates.id

        JOIN jobs
        ON applications.job_id =
           jobs.id

        ORDER BY applications.id DESC

    """).fetchall()

    candidates_list = conn.execute("""
        SELECT *
        FROM candidates
        ORDER BY name
    """).fetchall()

    jobs_list = conn.execute("""
        SELECT *
        FROM jobs
        ORDER BY title
    """).fetchall()

    conn.close()

    content = """

<h1>📋 Application Management</h1>

<div class="card">

<h2>➕ Create New Application</h2>

<form method="POST"
action="/create-application">

<label>Candidate</label>

<select name="candidate_id" required>

<option value="">
-- Select Candidate --
</option>
"""

    for c in candidates_list:

        content += f"""

<option value="{c['id']}">
{c['name']} - {c['target_role']}
</option>

"""

    content += """

</select>

<label>Job</label>

<select name="job_id" required>

<option value="">
-- Select Job --
</option>
"""

    for job in jobs_list:

        content += f"""

<option value="{job['id']}">
{job['title']} - {job['company']}
</option>

"""

    content += """

</select>

<button type="submit">
✨ Generate Application
</button>

</form>

</div>

<div class="card">

<h2>📋 Application Tracker</h2>

"""

    if not applications_list:

        content += """
<p>No applications created yet.</p>
"""

    else:

        content += """

<div class="table-wrap">

<table>

<tr>

<th>Candidate</th>
<th>Job</th>
<th>Company</th>
<th>Match</th>
<th>Status</th>
<th>Interview</th>
<th>Created</th>
<th>Action</th>

</tr>
"""

        for a in applications_list:

            content += f"""

<tr>

<td>
{a['candidate_name']}
</td>

<td>
{a['job_title']}
</td>

<td>
{a['job_company']}
</td>

<td>
<b>{a['match_score']}%</b>
</td>

<td>

<form method="POST"
action="/application/{a['id']}/status">

<select name="status"
onchange="this.form.submit()">

"""

            statuses = [
                "Saved",
                "Applied",
                "Shortlisted",
                "Interview",
                "Rejected",
                "Selected"
            ]

            for status in statuses:

                selected = ""

                if a["status"] == status:
                    selected = "selected"

                content += f"""

<option
value="{status}"
{selected}
>
{status}
</option>

"""

            content += f"""

</select>

</form>

</td>

<td>
{a['interview_date'] or 'Not scheduled'}
</td>

<td>
{a['created_at']}
</td>

<td>

<a
class="button"
href="/application/{a['id']}"
>
View
</a>

<a
class="button green"
href="/application/{a['id']}/auto-schedule"
>
Auto Schedule
</a>

<a
class="button secondary"
href="/application/{a['id']}/schedule"
>
Schedule
</a>

</td>

</tr>

"""

        content += """
</table>
</div>
"""

    content += "</div>"

    return render_page(content)


# =========================================================
# CREATE APPLICATION
# =========================================================

@app.route(
    "/create-application",
    methods=["POST"]
)
def create_application():

    candidate_id = request.form.get(
        "candidate_id"
    )

    job_id = request.form.get(
        "job_id"
    )

    conn = db()

    candidate = conn.execute(
        "SELECT * FROM candidates WHERE id=?",
        (candidate_id,)
    ).fetchone()

    job = conn.execute(
        "SELECT * FROM jobs WHERE id=?",
        (job_id,)
    ).fetchone()

    conn.close()

    if not candidate or not job:

        return "Candidate or job not found."

    score, matched, missing = calculate_match(
        candidate,
        job
    )

    resume = make_resume(
        candidate,
        job,
        matched
    )

    cover = make_cover_letter(
        candidate,
        job,
        matched
    )

    answers = make_answers(
        candidate,
        job
    )

    email = make_email(
        candidate,
        job,
        matched
    )

    conn = db()

    conn.execute("""
        INSERT INTO applications

        (
            candidate_id,
            job_id,
            match_score,
            matched_skills,
            missing_skills,
            resume,
            cover_letter,
            answers,
            recruiter_email,
            status,
            created_at
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

    """, (

        candidate_id,

        job_id,

        score,

        ", ".join(matched),

        ", ".join(missing),

        resume,

        cover,

        answers,

        email,

        "Saved",

        datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )

    ))

    conn.commit()

    application_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    conn.close()

    return redirect(
        url_for(
            "view_application",
            application_id=application_id
        )
    )


# =========================================================
# VIEW APPLICATION
# =========================================================

@app.route("/application/<int:application_id>")
def view_application(application_id):

    conn = db()

    application = conn.execute("""
        SELECT
            applications.*,
            candidates.name AS candidate_name,
            candidates.email AS candidate_email,
            candidates.phone AS candidate_phone,
            jobs.title AS job_title,
            jobs.company AS company,
            jobs.location AS job_location
        FROM applications
        JOIN candidates
            ON applications.candidate_id = candidates.id
        JOIN jobs
            ON applications.job_id = jobs.id
        WHERE applications.id = ?
    """, (application_id,)).fetchone()

    conn.close()

    if not application:
        return "Application not found.", 404

    status_options = [
        "Saved", "Applied", "Shortlisted",
        "Interview", "Rejected", "Selected"
    ]

    status_options_html = "".join(
        f'<option value="{status}" {'selected' if application["status"] == status else ''}>{status}</option>'
        for status in status_options
    )

    content = f"""

    <div class="card">
        <h1>📄 Application #{application['id']}</h1>
        <p><b>Candidate:</b> {application['candidate_name']}</p>
        <p><b>Job:</b> {application['job_title']} at {application['company']}</p>
        <p><b>Location:</b> {application['job_location'] or 'Not specified'}</p>

        <div class="stats">
            <div class="stat">
                <h2>{application['match_score']}%</h2>
                <p>🎯 Match Score</p>
            </div>
            <div class="stat">
                <h2>{application['status']}</h2>
                <p>📌 Current Status</p>
            </div>
            <div class="stat">
                <h2>{application['interview_date'] or '—'}</h2>
                <p>📅 Interview</p>
            </div>
        </div>

        <h3>📌 Update Application Status</h3>
        <form method="POST" action="/application/{application_id}/status">
            <select name="status">
                {status_options_html}
            </select>
            <button type="submit">Save Status</button>
        </form>
    </div>

    <div class="card">
        <h2>🧠 AI-Style Job Match Analysis</h2>
        <p><b>Matching skills:</b> {application['matched_skills'] or 'None'}</p>
        <p><b>Missing skills:</b> {application['missing_skills'] or 'None'}</p>
    </div>

    <div class="card">
        <h2>📄 Customized Resume Content</h2>
        <p>This resume content is customized for this candidate and the selected job.</p>
        <pre>{application['resume'] or 'No customized resume generated yet.'}</pre>
    </div>

    <div class="card">
        <h2>✉️ Cover Letter</h2>
        <pre>{application['cover_letter'] or 'No cover letter generated yet.'}</pre>
    </div>

    <div class="card">
        <h2>❓ Interview / Application Answers</h2>
        <pre>{application['answers'] or 'No interview answers generated yet.'}</pre>
    </div>

    <div class="card">
        <h2>📨 Recruiter Email</h2>
        <pre>{application['recruiter_email'] or 'No recruiter email generated yet.'}</pre>
    </div>

    <div class="card">
        <h2>📅 Interview Scheduling</h2>
        <p><b>Current interview:</b> {application['interview_date'] or 'Not scheduled'}</p>

        <a class="button green" href="/application/{application_id}/auto-schedule">
            ⚡ Automatic Scheduling
        </a>

        <a class="button secondary" href="/application/{application_id}/schedule">
            📅 Manual Scheduling
        </a>
    </div>

    <div class="card">
        <h2>🔄 Application Actions</h2>

        <a class="button" href="/application/{application_id}/regenerate">
            ✨ Regenerate Application Documents
        </a>

        <a class="button secondary" href="/applications">
            ← Back to Application Tracker
        </a>
    </div>

    """

    return render_page(content)


@app.route("/application/<int:application_id>/regenerate")
def regenerate_application(application_id):
    """Regenerate resume, cover letter, answers and recruiter email."""

    conn = db()

    application = conn.execute("""
        SELECT * FROM applications WHERE id = ?
    """, (application_id,)).fetchone()

    if not application:
        conn.close()
        return "Application not found.", 404

    candidate = conn.execute("""
        SELECT * FROM candidates WHERE id = ?
    """, (application["candidate_id"],)).fetchone()

    job = conn.execute("""
        SELECT * FROM jobs WHERE id = ?
    """, (application["job_id"],)).fetchone()

    if not candidate or not job:
        conn.close()
        return "Candidate or job not found.", 404

    score, matched, missing = calculate_match(candidate, job)

    resume = make_resume(candidate, job, matched)
    cover = make_cover_letter(candidate, job, matched)
    answers = make_answers(candidate, job)
    email = make_email(candidate, job, matched)

    conn.execute("""
        UPDATE applications
        SET
            match_score = ?,
            matched_skills = ?,
            missing_skills = ?,
            resume = ?,
            cover_letter = ?,
            answers = ?,
            recruiter_email = ?
        WHERE id = ?
    """, (
        score,
        ", ".join(matched),
        ", ".join(missing),
        resume,
        cover,
        answers,
        email,
        application_id
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("view_application", application_id=application_id))


# =========================================================
# CHANGE APPLICATION STATUS
# =========================================================

@app.route(
    "/application/<int:application_id>/status",
    methods=["POST"]
)
def change_status(application_id):

    status = request.form.get(
        "status"
    )

    allowed = [
        "Saved",
        "Applied",
        "Shortlisted",
        "Interview",
        "Rejected",
        "Selected"
    ]

    if status not in allowed:

        status = "Saved"

    conn = db()

    conn.execute("""
        UPDATE applications
        SET status=?
        WHERE id=?
    """, (
        status,
        application_id
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for("applications")
    )


# =========================================================
# INTERVIEW SCHEDULING
# =========================================================

@app.route("/application/<int:application_id>/auto-schedule")
def auto_schedule(application_id):
    date = next_business_day(2)
    conn = db()
    conn.execute("UPDATE applications SET interview_date=?, status=? WHERE id=?", (date, "Interview", application_id))
    conn.commit()
    conn.close()
    return redirect(url_for("view_application", application_id=application_id))


@app.route("/application/<int:application_id>/schedule", methods=["GET", "POST"])
def schedule_interview(application_id):
    if request.method == "POST":
        interview_date = request.form.get("interview_date")
        conn = db()
        conn.execute("UPDATE applications SET interview_date=?, status=? WHERE id=?", (interview_date, "Interview", application_id))
        conn.commit()
        conn.close()
        return redirect(url_for("view_application", application_id=application_id))

    content = f"""
<h1>📅 Schedule Interview</h1>
<div class="card">
<form method="POST">
<label>Interview Date & Time</label>
<input type="datetime-local" name="interview_date" required>
<button type="submit">Confirm Interview</button>
<a class="button secondary" href="/application/{application_id}">Cancel</a>
</form>
</div>
"""
    return render_page(content)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# =========================================================
# ANALYTICS
# =========================================================

@app.route("/analytics")
def analytics():

    conn = db()

    total = conn.execute(
        "SELECT COUNT(*) FROM applications"
    ).fetchone()[0]

    saved = conn.execute("""
        SELECT COUNT(*)
        FROM applications
        WHERE status='Saved'
    """).fetchone()[0]

    applied = conn.execute("""
        SELECT COUNT(*)
        FROM applications
        WHERE status='Applied'
    """).fetchone()[0]

    shortlisted = conn.execute("""
        SELECT COUNT(*)
        FROM applications
        WHERE status='Shortlisted'
    """).fetchone()[0]

    interviews = conn.execute("""
        SELECT COUNT(*)
        FROM applications
        WHERE status='Interview'
    """).fetchone()[0]

    rejected = conn.execute("""
        SELECT COUNT(*)
        FROM applications
        WHERE status='Rejected'
    """).fetchone()[0]

    selected = conn.execute("""
        SELECT COUNT(*)
        FROM applications
        WHERE status='Selected'
    """).fetchone()[0]

    average = conn.execute("""
        SELECT AVG(match_score)
        FROM applications
    """).fetchone()[0]

    conn.close()

    average = round(
        average or 0,
        1
    )

    content = f"""

<h1>📈 Analytics</h1>

<div class="stats">

<div class="stat">
<h2>{total}</h2>
<p>Total Applications</p>
</div>

<div class="stat">
<h2>{applied}</h2>
<p>Applied</p>
</div>

<div class="stat">
<h2>{shortlisted}</h2>
<p>Shortlisted</p>
</div>

<div class="stat">
<h2>{interviews}</h2>
<p>Interviews</p>
</div>

</div>

<div class="stats">

<div class="stat">
<h2>{selected}</h2>
<p>Selected</p>
</div>

<div class="stat">
<h2>{rejected}</h2>
<p>Rejected</p>
</div>

<div class="stat">
<h2>{saved}</h2>
<p>Saved</p>
</div>

<div class="stat">
<h2>{average}%</h2>
<p>Average Match</p>
</div>

</div>

<div class="card">

<h2>📊 Application Pipeline</h2>

<p>
Saved → Applied → Shortlisted → Interview → Selected
</p>

<div style="
background:#e5e7eb;
height:30px;
border-radius:8px;
overflow:hidden;
">

<div style="
background:#2563eb;
height:30px;
width:{min(100, total * 10)}%;
">
</div>

</div>

<br>

<p>
The analytics page helps track the candidate
application pipeline and overall job-search activity.
</p>

</div>

"""

    return render_page(content)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    print()
    print("========================================")
    print("       JOB AUTOMATION AGENT")
    print("========================================")
    print()
    print("Open this in your browser:")
    print()
    print("http://127.0.0.1:5000")
    print()
    print("Press CTRL+C to stop the server.")
    print("========================================")
    print()

    app.run(
        debug=True,
        port=5000
    )