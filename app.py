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


# =========================================================
# 1️ Hàm kết nối database (auto detect)
# =========================================================
def get_connection():
    db_url = os.getenv("DATABASE_URL", "sqlite:///employee.db")

    if db_url.startswith("postgresql://"):
        print("Connecting to PostgreSQL (Render)...")
        conn = psycopg2.connect(db_url)
    else:
        print("Using local SQLite database...")
        db_path = db_url.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)

    return conn


# =========================================================
# 2️ Hàm khởi tạo database (nếu chưa có)
# =========================================================
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


# =========================================================
# 3️ Routes
# =========================================================
@app.route("/")
def index():
    return render_template("form.html")


@app.route("/employees")
def employees():
    conn = get_connection()
    conn.row_factory = sqlite3.Row if isinstance(conn, sqlite3.Connection) else None
    c = conn.cursor()
    c.execute("SELECT * FROM employee ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("employees.html", rows=rows)


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

    # Bỏ qua strategic/talent/teamwork nếu là Officer hoặc Senior
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
    c = conn.cursor()
    c.execute('''
        INSERT INTO employee (
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
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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


# --- Upload Excel ---
@app.route("/upload", methods=["POST"])
def upload_excel():
    file = request.files.get("file")
    if not file:
        return "No file uploaded", 400

    df = pd.read_excel(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.fillna("")

    conn = get_connection()
    c = conn.cursor()

    for _, row in df.iterrows():
        try:
            def safe_int(val):
                try:
                    val = int(val)
                    return min(max(val, 1), 5)
                except:
                    return None

            core = {
                "communication": safe_int(row.get("communication")),
                "continuous_learning": safe_int(row.get("continuous_learning")),
                "critical_thinking": safe_int(row.get("critical_thinking")),
                "data_analysis": safe_int(row.get("data_analysis")),
                "digital_literacy": safe_int(row.get("digital_literacy")),
                "problem_solving": safe_int(row.get("problem_solving")),
                "strategic_thinking": safe_int(row.get("strategic_thinking")),
                "talent_management": safe_int(row.get("talent_management")),
                "teamwork_leadership": safe_int(row.get("teamwork_leadership")),
            }

            core_req = {
                "communication_req": safe_int(row.get("communication_req")),
                "continuous_learning_req": safe_int(row.get("continuous_learning_req")),
                "critical_thinking_req": safe_int(row.get("critical_thinking_req")),
                "data_analysis_req": safe_int(row.get("data_analysis_req")),
                "digital_literacy_req": safe_int(row.get("digital_literacy_req")),
                "problem_solving_req": safe_int(row.get("problem_solving_req")),
                "strategic_thinking_req": safe_int(row.get("strategic_thinking_req")),
                "talent_management_req": safe_int(row.get("talent_management_req")),
                "teamwork_leadership_req": safe_int(row.get("teamwork_leadership_req")),
            }

            new = {
                "creative_thinking": safe_int(row.get("creative_thinking")),
                "resilience": safe_int(row.get("resilience")),
                "ai_bigdata": safe_int(row.get("ai_bigdata")),
                "analytical_thinking": safe_int(row.get("analytical_thinking")),
            }

            new_req = {
                "creative_thinking_req": safe_int(row.get("creative_thinking_req")),
                "resilience_req": safe_int(row.get("resilience_req")),
                "ai_bigdata_req": safe_int(row.get("ai_bigdata_req")),
                "analytical_thinking_req": safe_int(row.get("analytical_thinking_req")),
            }

            def classify(scores_dict, title):
                vals = []
                for k, v in scores_dict.items():
                    if title in ["Officer", "Senior"] and k in [
                        "strategic_thinking", "talent_management", "teamwork_leadership"
                    ]:
                        continue
                    if v:
                        vals.append(v)
                if not vals:
                    return "N/A"
                pct = (sum(vals) / (len(vals) * 5)) * 100
                if pct < 70:
                    return "Low"
                elif pct > 90:
                    return "High"
                return "Medium"

            class_core = classify(core, row.get("title"))
            class_new = classify(new, row.get("title"))

            c.execute('''
                INSERT INTO employee (
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
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                row.get("year"), row.get("code"), row.get("full_name"), row.get("title"),
                row.get("department"), row.get("division"),
                *core.values(), *core_req.values(),
                *new.values(), *new_req.values(),
                class_core, class_new
            ))

        except Exception as e:
            print(f"Upload error: {e}")

    conn.commit()
    conn.close()
    print("Upload completed successfully.")
    return redirect(url_for("employees"))


# --- Download template ---
@app.route("/download-template")
def download_template():
    file_path = os.path.join(app.root_path, "static", "employee_template.xlsx")
    return send_file(file_path, as_attachment=True)


# --- Export Excel ---
@app.route("/export")
def export_data():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM employee ORDER BY id DESC", conn)
    conn.close()

    output_path = os.path.join(app.root_path, "static", "employee_data.xlsx")
    df.to_excel(output_path, index=False)
    return send_file(output_path, as_attachment=True)


# --- Delete selected ---
@app.route("/delete-selected", methods=["POST"])
def delete_selected():
    selected_ids = request.form.getlist("selected_ids")
    if not selected_ids:
        return redirect(url_for("employees"))

    try:
        conn = get_connection()
        c = conn.cursor()
        placeholders = ",".join("?" if isinstance(conn, sqlite3.Connection) else "%s" for _ in selected_ids)
        query = f"DELETE FROM employee WHERE id IN ({placeholders})"
        c.execute(query, selected_ids)
        conn.commit()
        conn.close()
        print(f"🗑 Deleted {len(selected_ids)} records.")
    except Exception as e:
        print("Delete error:", e)

    return redirect(url_for("employees"))


# --- API for Power BI ---
@app.route("/api/employees")
def api_employees():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM employee")
    columns = [desc[0] for desc in c.description]
    data = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return jsonify(data)


# =========================================================
# 4 Main
# =========================================================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
