from flask import Flask, render_template, request, redirect, send_file, url_for, jsonify
import os
import pandas as pd
import sqlite3
import psycopg2
from urllib.parse import urlparse
from datetime import datetime
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = "your_secret"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Load environment variables ---
load_dotenv()



# 1️ Connect database (auto detect)

def get_connection():
    db_url = os.getenv("DATABASE_URL", "sqlite:///employee.db")

    if db_url.startswith("postgresql://"):
        print(" Connecting to PostgreSQL (Render)...")
        conn = psycopg2.connect(db_url)
    else:
        print("Using local SQLite database...")
        db_path = db_url.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)

    return conn



# 2️ Helper: Placeholder cho query

def get_placeholder(conn, count):
    if isinstance(conn, sqlite3.Connection):
        return ",".join(["?"] * count)
    else:
        return ",".join(["%s"] * count)



# 3️ Initialize a database
def init_db():
    conn = get_connection()
    c = conn.cursor()

    if isinstance(conn, sqlite3.Connection):
        id_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
    else:
        id_type = "SERIAL PRIMARY KEY"

    c.execute(f'''
    CREATE TABLE IF NOT EXISTS employee (
        id {id_type},
        year TEXT,
        code TEXT,
        full_name TEXT,
        title TEXT,
        department TEXT,
        division TEXT,

        -- Core competencies
        communication INTEGER,
        continuous_learning INTEGER,
        critical_thinking INTEGER,
        data_analysis INTEGER,
        digital_literacy INTEGER,
        problem_solving INTEGER,
        strategic_thinking INTEGER,
        talent_management INTEGER,
        teamwork_leadership INTEGER,

        -- Core competencies (req)
        communication_req INTEGER,
        continuous_learning_req INTEGER,
        critical_thinking_req INTEGER,
        data_analysis_req INTEGER,
        digital_literacy_req INTEGER,
        problem_solving_req INTEGER,
        strategic_thinking_req INTEGER,
        talent_management_req INTEGER,
        teamwork_leadership_req INTEGER,

        -- New competencies
        creative_thinking INTEGER,
        resilience INTEGER,
        ai_bigdata INTEGER,
        analytical_thinking INTEGER,

        -- New competencies (req)
        creative_thinking_req INTEGER,
        resilience_req INTEGER,
        ai_bigdata_req INTEGER,
        analytical_thinking_req INTEGER,

        classification_core TEXT,
        classification_new TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()


# 4️ Routes

@app.route("/")
def index():
    return render_template("form.html")


# --- Hiển thị danh sách nhân viên ---
@app.route("/employees")
def employees():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM public.employee ORDER BY id DESC")

    columns = [desc[0] for desc in c.description]
    rows = [dict(zip(columns, row)) for row in c.fetchall()]

    conn.close()
    return render_template("employees.html", rows=rows)


# --- Gửi form thêm nhân viên ---
@app.route("/submit", methods=["POST"])
def submit():
    f = request.form
    year = f.get("year")
    code = f.get("code")
    full_name = f.get("full_name")
    title = f.get("title")
    department = f.get("department")
    division = f.get("division")

    def safe_int(v):
        try:
            return min(max(int(v), 1), 5)
        except:
            return None

    all_fields = [
        "communication", "continuous_learning", "critical_thinking",
        "data_analysis", "digital_literacy", "problem_solving",
        "strategic_thinking", "talent_management", "teamwork_leadership",
        "communication_req", "continuous_learning_req", "critical_thinking_req",
        "data_analysis_req", "digital_literacy_req", "problem_solving_req",
        "strategic_thinking_req", "talent_management_req", "teamwork_leadership_req",
        "creative_thinking", "resilience", "ai_bigdata", "analytical_thinking",
        "creative_thinking_req", "resilience_req", "ai_bigdata_req", "analytical_thinking_req"
    ]

    data = {k: safe_int(f.get(k)) for k in all_fields}

    # Ẩn 3 competency nếu là Officer hoặc Senior
    if title in ["Officer", "Senior"]:
        skip_fields = [
            "strategic_thinking", "talent_management", "teamwork_leadership",
            "strategic_thinking_req", "talent_management_req", "teamwork_leadership_req"
        ]
        for k in skip_fields:
            data[k] = None

    def classify(keys):
        vals = [data[k] for k in keys if data[k] is not None]
        if not vals:
            return "N/A"
        pct = (sum(vals) / (len(vals) * 5)) * 100
        if pct < 70:
            return "Low"
        elif pct > 90:
            return "High"
        return "Medium"

    if title in ["Officer", "Senior"]:
        core_keys = [
            "communication", "continuous_learning", "critical_thinking",
            "data_analysis", "digital_literacy", "problem_solving"
        ]
    else:
        core_keys = [
            "communication", "continuous_learning", "critical_thinking",
            "data_analysis", "digital_literacy", "problem_solving",
            "strategic_thinking", "talent_management", "teamwork_leadership"
        ]

    class_core = classify(core_keys)
    class_new = classify(["creative_thinking", "resilience", "ai_bigdata", "analytical_thinking"])

    conn = get_connection()
    placeholders = get_placeholder(conn, 34)
    c = conn.cursor()
    c.execute(f'''
        INSERT INTO public.employee (
            year, code, full_name, title, department, division,
            communication, continuous_learning, critical_thinking,
            data_analysis, digital_literacy, problem_solving,
            strategic_thinking, talent_management, teamwork_leadership,
            communication_req, continuous_learning_req, critical_thinking_req,
            data_analysis_req, digital_literacy_req, problem_solving_req,
            strategic_thinking_req, talent_management_req, teamwork_leadership_req,
            creative_thinking, resilience, ai_bigdata, analytical_thinking,
            creative_thinking_req, resilience_req, ai_bigdata_req, analytical_thinking_req,
            classification_core, classification_new
        )
        VALUES ({placeholders})
    ''', (
        year, code, full_name, title, department, division,
        *[data[k] for k in all_fields[:9]],
        *[data[k] for k in all_fields[9:18]],
        *[data[k] for k in all_fields[18:22]],
        *[data[k] for k in all_fields[22:26]],
        class_core, class_new
    ))

    conn.commit()
    conn.close()
    return redirect("/employees")


# --- Delete employees have been selected ---
@app.route("/delete-selected", methods=["POST"])
def delete_selected():
    selected_ids = request.form.getlist("selected_ids")
    if not selected_ids:
        return redirect(url_for("employees"))

    conn = get_connection()
    c = conn.cursor()

    placeholder = get_placeholder(conn, len(selected_ids))
    c.execute(f"DELETE FROM public.employee WHERE id IN ({placeholder})", selected_ids)

    conn.commit()
    conn.close()
    print(f"🗑 Deleted {len(selected_ids)} employees.")
    return redirect(url_for("employees"))



# 5️ API + Export
@app.route("/api/employees")
def api_employees():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM public.employee ORDER BY id DESC")
    columns = [desc[0] for desc in c.description]
    data = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return jsonify(data)


@app.route("/export")
def export_data():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM public.employee ORDER BY id DESC", conn)
    conn.close()

    output_path = os.path.join(app.root_path, "static", "employee_data.xlsx")
    df.to_excel(output_path, index=False)
    return send_file(output_path, as_attachment=True)



# 6️ MAIN ENTRY

if __name__ == "__main__":
    # init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
