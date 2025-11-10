from flask import Flask, render_template, request, redirect, send_file, url_for, jsonify
import sqlite3
import pandas as pd
import os
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "your_secret"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Khởi tạo DB ---
def init_db():
    conn = sqlite3.connect('employee.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS employee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()


# --- Helper ---
def safe_int(val):
    """Ép kiểu về int trong khoảng 1–5"""
    try:
        i = int(val)
        return max(min(i, 5), 1)
    except (ValueError, TypeError):
        return None


# === ROUTES ===
@app.route("/")
def index():
    return render_template("form.html")

@app.route("/employees")
def employees():
    conn = sqlite3.connect("employee.db")
    conn.row_factory = sqlite3.Row
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

    # --- Bỏ qua Strategic/Talent/Teamwork nếu là Officer hoặc Senior ---
    if title in ["Officer", "Senior"]:
        skip_fields = [
            "strategic_thinking", "talent_management", "teamwork_leadership",
            "strategic_thinking_req", "talent_management_req", "teamwork_leadership_req"
        ]
        for k in skip_fields:
            data[k] = None  # bỏ qua, không lưu

    # --- Phân loại điểm ---
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

    # Nếu là Officer/Senior thì loại 3 competency ra khỏi tính trung bình
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

    # --- Lưu DB ---
    conn = sqlite3.connect("employee.db")
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

    # Đọc file Excel
    df = pd.read_excel(file)
    df.columns = [str(c).strip().lower() for c in df.columns]
    print("Columns in Excel:", list(df.columns))

    df = df.fillna("")

    conn = sqlite3.connect("employee.db")
    c = conn.cursor()

    for _, row in df.iterrows():
        try:
            # --- Helper: ép kiểu an toàn ---
            def safe_int(val):
                try:
                    val = int(val)
                    return min(max(val, 1), 5)
                except:
                    return None

            # --- Core Competencies ---
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

            # --- Core Competencies (req) ---
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

            # --- New Competencies ---
            new = {
                "creative_thinking": safe_int(row.get("creative_thinking")),
                "resilience": safe_int(row.get("resilience")),
                "ai_bigdata": safe_int(row.get("ai_bigdata")),
                "analytical_thinking": safe_int(row.get("analytical_thinking")),
            }

            # --- New Competencies (req) ---
            new_req = {
                "creative_thinking_req": safe_int(row.get("creative_thinking_req")),
                "resilience_req": safe_int(row.get("resilience_req")),
                "ai_bigdata_req": safe_int(row.get("ai_bigdata_req")),
                "analytical_thinking_req": safe_int(row.get("analytical_thinking_req")),
            }

            # --- Tính phân loại ---
            def classify(scores_dict, title):
                vals = []
                for k, v in scores_dict.items():
                    # Nếu là Officer hoặc Senior thì bỏ 3 competency này
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

            # --- Insert vào DB ---
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

# --- Download Template ---
@app.route("/download-template")
def download_template():
    file_path = os.path.join(app.root_path, "static", "employee_template.xlsx")
    return send_file(file_path, as_attachment=True)

# --- Export Excel ---
@app.route("/export")
def export_data():
    conn = sqlite3.connect("employee.db")
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
        conn = sqlite3.connect("employee.db")
        c = conn.cursor()
        placeholders = ",".join("?" for _ in selected_ids)
        c.execute(f"DELETE FROM employee WHERE id IN ({placeholders})", selected_ids)
        conn.commit()
        conn.close()
        print(f"Deleted {len(selected_ids)} records.")
    except Exception as e:
        print(" Delete error:", e)

    return redirect(url_for("employees"))


# --- API for Power BI ---
@app.route("/api/employees")
def api_employees():
    conn = sqlite3.connect("employee.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM employee")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# @app.route("/seed")
# def seed():
#     conn = sqlite3.connect("employee.db")
#     c = conn.cursor()

#     titles = ["Officer", "Senior", "Manager", "Deputy Manager"]
#     departments = ["System Department", "Software Development", "IT Division", "Secretariat"]
#     divisions = ["BOM1", "BOM2", "Product Department", "Finance Division"]

#     # --- Helper ---
#     def rand_score():
#         return random.randint(1, 5)

#     def classify(scores, title):
#         vals = scores[:]
#         if title in ["Officer", "Senior"]:
#             vals = vals[:6]  # bỏ 3 competency
#         pct = (sum(vals) / (len(vals) * 5)) * 100
#         if pct < 70:
#             return "Low"
#         elif pct > 90:
#             return "High"
#         return "Medium"

#     # --- Tạo 50 nhân viên ---
#     for i in range(1, 10):
#         title = random.choice(titles)
#         department = random.choice(departments)
#         division = random.choice(divisions)
#         full_name = random.choice([
#             "Nguyễn An", "Trần Vy", "Lê Minh", "Phạm Huy", "Hoàng Lan",
#             "Võ Tâm", "Lý Quân", "Ngô Bình", "Đặng Mai", "Phan Long",
#             "Bùi Dương", "Huỳnh Khoa", "Đỗ Vy", "Vũ Nam", "Trịnh Anh",
#             "Trần Hà", "Lâm Hạnh", "Lê Hòa", "Nguyễn Tú", "Hoàng Bảo"
#         ])

#         core = [rand_score() for _ in range(9)]
#         core_req = [rand_score() for _ in range(9)]
#         new = [rand_score() for _ in range(4)]
#         new_req = [rand_score() for _ in range(4)]

#         class_core = classify(core, title)
#         class_new = classify(new, title)

#         c.execute('''
#             INSERT INTO employee (
#                 year, code, full_name, title, department, division,
#                 communication, continuous_learning, critical_thinking,
#                 data_analysis, digital_literacy, problem_solving,
#                 strategic_thinking, talent_management, teamwork_leadership,
#                 communication_req, continuous_learning_req, critical_thinking_req,
#                 data_analysis_req, digital_literacy_req, problem_solving_req,
#                 strategic_thinking_req, talent_management_req, teamwork_leadership_req,
#                 creative_thinking, resilience, ai_bigdata, analytical_thinking,
#                 creative_thinking_req, resilience_req, ai_bigdata_req, analytical_thinking_req,
#                 classification_core, classification_new
#             )
#             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
#         ''', (
#             2025, f"E{i:03}", full_name, title,
#             department, division,
#             *core, *core_req, *new, *new_req,
#             class_core, class_new
#         ))

#     conn.commit()
#     conn.close()
#     return redirect(url_for("employees"))

# --- MAIN ---
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
