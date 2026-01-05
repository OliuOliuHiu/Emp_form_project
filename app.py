from flask import Flask, render_template, request, redirect, send_file, url_for, jsonify, flash, session
import tempfile
import os
import pandas as pd
import sqlite3
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Load environment variables ---
load_dotenv()


# Connect database 
def get_connection():
    from urllib.parse import urlparse
    import ssl

    db_url = os.getenv("DATABASE_URL", "sqlite:///employee.db")

    if db_url.startswith("postgresql://"):
        print("Connecting to PostgreSQL (host)...")
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        if "sslmode" not in db_url:
            db_url += "?sslmode=require"

        conn = psycopg2.connect(db_url, sslmode="require")
    else:
        # Local SQLite
        print("Using local SQLite database...")
        db_path = db_url.replace("sqlite:///", "")
        conn = sqlite3.connect(
            db_path,
            timeout=10,              
            check_same_thread=False  
        )
        conn.execute("PRAGMA busy_timeout = 5000")  

    return conn


# 2️ Helper: placeholder match with database
def get_placeholder(conn, count):
    if isinstance(conn, sqlite3.Connection):
        return ",".join(["?"] * count)
    else:
        return ",".join(["%s"] * count)


# 3️ Initialize a database 
def init_db():
    conn = get_connection()
    c = conn.cursor()

    id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if isinstance(conn, sqlite3.Connection) else "SERIAL PRIMARY KEY"
    c.execute(f"""
    CREATE TABLE IF NOT EXISTS employee (
        id {id_type},
        year TEXT,
        code TEXT,
        full_name TEXT,
        title TEXT,
        department TEXT,
        division TEXT,

        communication REAL,
        continuous_learning REAL,
        critical_thinking REAL,
        data_analysis REAL,
        digital_literacy REAL,
        problem_solving REAL,
        strategic_thinking REAL,
        talent_management REAL,
        teamwork_leadership REAL,

        communication_req REAL,
        continuous_learning_req REAL,
        critical_thinking_req REAL,
        data_analysis_req REAL,
        digital_literacy_req REAL,
        problem_solving_req REAL,
        strategic_thinking_req REAL,
        talent_management_req REAL,
        teamwork_leadership_req REAL,

        creative_thinking REAL,
        resilience REAL,
        ai_bigdata REAL,
        analytical_thinking REAL,

        creative_thinking_req REAL,
        resilience_req REAL,
        ai_bigdata_req REAL,
        analytical_thinking_req REAL,

        classification_core TEXT,
        classification_new TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()


# 4️ ROUTES
@app.route("/")
def index():
    form_data = session.pop("form_data", None)
    return render_template("form.html", form_data=form_data)

# --- Employee List + Search Icon ---
@app.route("/employees")
def employees():
    search = request.args.get("search", "").strip()
    conn = get_connection()
    c = conn.cursor()

    # PostgreSQL need schema to "public."
    table_name = "public.employee" if not isinstance(conn, sqlite3.Connection) else "employee"

    if search:
        query = f"SELECT * FROM {table_name} WHERE full_name ILIKE %s OR code ILIKE %s OR division ILIKE %s OR department ILIKE %s ORDER BY id DESC" \
            if not isinstance(conn, sqlite3.Connection) else \
            f"SELECT * FROM {table_name} WHERE full_name LIKE ? OR code LIKE ? OR division LIKE ? OR department LIKE ? ORDER BY id DESC"
        c.execute(query, (f"%{search}%", f"%{search}%",f"%{search}%",f"%{search}%"))
    else:
        c.execute(f"SELECT * FROM {table_name} ORDER BY id DESC")

    columns = [desc[0] for desc in c.description]
    rows = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()

    return render_template("employees.html", rows=rows, search=search)

# --- \Add member ---
@app.route("/submit", methods=["POST"])
def submit():
    from statistics import stdev
    f = request.form
    year, code, full_name = f.get("year"), f.get("code"), f.get("full_name")
    title, department, division = f.get("title"), f.get("department"), f.get("division")

    def safe_float(v):
        try:
            val = float(v)
            if 1.0 <= val <= 5.0:
                return round(val,1)
        except:
            pass
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
    data = {k: safe_float(f.get(k)) for k in all_fields}

    if title in ["Officer", "Senior"]:
        for k in ["strategic_thinking", "talent_management", "teamwork_leadership",
                  "strategic_thinking_req", "talent_management_req", "teamwork_leadership_req"]:
            data[k] = None

    core_keys = ["communication", "continuous_learning", "critical_thinking",
                 "data_analysis", "digital_literacy", "problem_solving"]
    core_req_keys = ["communication_req", "continuous_learning_req", "critical_thinking_req",
                     "data_analysis_req", "digital_literacy_req", "problem_solving_req"]

    if title not in ["Officer", "Senior"]:
        core_keys += ["strategic_thinking", "talent_management", "teamwork_leadership"]
        core_req_keys += ["strategic_thinking_req", "talent_management_req", "teamwork_leadership_req"]

    new_keys = ["creative_thinking", "resilience", "ai_bigdata", "analytical_thinking"]
    new_req_keys = ["creative_thinking_req", "resilience_req", "ai_bigdata_req", "analytical_thinking_req"]

    missing_core = [k for k in core_keys + core_req_keys if data.get(k) is None]
    if missing_core:
        flash("Core competencies must not be empty and must be between 1.0 and 5.0", "danger")
        session["form_data"] = request.form.to_dict()
        return redirect(url_for("index"))

    conn = get_connection()
    c = conn.cursor()
    table_name = "public.employee" if not isinstance(conn, sqlite3.Connection) else "employee"
    placeholders = get_placeholder(conn, 34)

    query_check = f"SELECT COUNT(*) FROM {table_name} WHERE LOWER(code) = %s AND year = %s" \
        if not isinstance(conn, sqlite3.Connection) else \
        f"SELECT COUNT(*) FROM {table_name} WHERE LOWER(code) = ? AND year = ?"
    c.execute(query_check, (code.lower(), year))
    if c.fetchone()[0] > 0:
        conn.close()
        flash(f"Employee code '{code}' already exists for year '{year}'.", "danger")
        session["form_data"] = request.form.to_dict()
        return redirect(url_for("index"))

    def calculate_pct(score_keys, req_keys):
        scores = [data[k] for k in score_keys if data[k] is not None]
        reqs = [data[k] for k in req_keys if data[k] is not None]
        if not scores or not reqs:
            return None
        total_score = sum(scores)
        total_req = sum(reqs)
        if total_req == 0:
            return None
        return (total_score / total_req) * 100

    pct_core = calculate_pct(core_keys, core_req_keys)
    pct_new = calculate_pct(new_keys, new_req_keys)

    c.execute(f"""
        INSERT INTO {table_name} (
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
    """, (
        year, code, full_name, title, department, division,
        *[data[k] for k in all_fields[:9]],
        *[data[k] for k in all_fields[9:18]],
        *[data[k] for k in all_fields[18:22]],
        *[data[k] for k in all_fields[22:26]],
        "Pending", "Pending"
    ))
    conn.commit()

    # Update classification for all employees
    update_classification_for_all(conn, table_name, core_keys, core_req_keys, "classification_core")
    update_classification_for_all(conn, table_name, new_keys, new_req_keys, "classification_new")

    conn.close()
    flash("Employee submitted and all classifications updated.", "success")
    return redirect("/employees")

def update_classification_for_all(conn, table_name, score_keys_all, req_keys_all, field_to_update):
    import statistics
    c = conn.cursor()

    # Lấy tất cả bản ghi cùng với title và các trường cần thiết
    c.execute(f"SELECT id, title, {', '.join(score_keys_all + req_keys_all)} FROM {table_name}")
    rows_raw = c.fetchall()

    rows = []
    for row in rows_raw:
        emp_id = row[0]
        title = row[1]
        values = dict(zip(score_keys_all + req_keys_all, row[2:]))

        if title in ["Officer", "Senior"]:
            # Chỉ cần 6 core
            keys = [
                "communication", "continuous_learning", "critical_thinking",
                "data_analysis", "digital_literacy", "problem_solving"
            ]
        else:
            # Đủ 9 core
            keys = score_keys_all

        req_keys = [k + "_req" for k in keys]

        # Lấy điểm thực và yêu cầu
        scores = [values.get(k) for k in keys if values.get(k) is not None]
        reqs = [values.get(k) for k in req_keys if values.get(k) is not None]

        # Nếu thiếu trường nào → bỏ qua dòng
        if len(scores) != len(keys) or len(reqs) != len(req_keys):
            continue

        total_score = sum(scores)
        total_req = sum(reqs)
        if total_req == 0:
            continue

        pct = (total_score / total_req) * 100
        rows.append((emp_id, pct))

    if len(rows) < 2:
        return

    pcts = [r[1] for r in rows]
    pct_min = min(pcts)
    pct_max = max(pcts)
    sd = statistics.stdev(pcts)
    high_thres = pct_max - sd
    low_thres = pct_min + sd

    for emp_id, pct in rows:
        if pct > high_thres:
            label = "High"
        elif pct < low_thres:
            label = "Low"
        else:
            label = "Medium"

        update_q = f"UPDATE {table_name} SET {field_to_update} = %s WHERE id = %s" \
            if not isinstance(conn, sqlite3.Connection) else \
            f"UPDATE {table_name} SET {field_to_update} = ? WHERE id = ?"
        c.execute(update_q, (label, emp_id))
    conn.commit()

@app.route("/upload", methods=["POST"])
def upload_excel():
    file = request.files.get("file")
    if not file:
        flash("No file selected.", "danger")
        return redirect(url_for("employees"))

    try:
        df = pd.read_excel(file)
    except Exception:
        flash("Invalid Excel file format.", "danger")
        return redirect(url_for("employees"))

    df.columns = [c.strip().lower() for c in df.columns]

    required_cols = ["year", "code", "full_name", "title", "department", "division"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        flash(f"Missing required columns: {', '.join(missing_cols)}", "danger")
        return redirect(url_for("employees"))

    def safe_float(v):
        try:
            val = float(v)
            if val < 1.0 or val > 5.0:
                return None
            return round(val,1)
        except:
            return None

    conn = get_connection()
    c = conn.cursor()
    table = "public.employee" if not isinstance(conn, sqlite3.Connection) else "employee"

    # Select Employee Code and Year list have storaged in DB
    c.execute(f"SELECT LOWER(code), year FROM {table}")
    existing_code_year = set((row[0], str(row[1])) for row in c.fetchall())

    # Create a temporary column to check duplicates in Excel file (code + year combination)
    df["_code_year"] = df.apply(
        lambda r: (str(r["code"]).strip().lower() if pd.notna(r["code"]) else "", 
                  str(r["year"]).strip() if pd.notna(r["year"]) else ""), 
        axis=1
    )
    # Count occurrences of each (code, year) combination
    code_year_counts = df["_code_year"].value_counts()

    success = 0
    skipped_details = []
    valid_rows = []
    rows_with_errors = []

    for idx, row in df.iterrows():
        errors = []

        code = str(row.get("code")).strip() if pd.notna(row.get("code")) else ""
        full_name = str(row.get("full_name")).strip() if pd.notna(row.get("full_name")) else ""
        title = str(row.get("title")).strip() if pd.notna(row.get("title")) else ""

        if not code:
            errors.append("Missing employee code")
        if not full_name:
            errors.append("Missing full name")

        year = str(row.get("year")).strip() if pd.notna(row.get("year")) else ""
        
        # Check code duplicated in Excel file (same code and year)
        current_code_year = (code.lower(), year)
        if code_year_counts.get(current_code_year, 0) > 1:
            errors.append(f"Duplicate code {code} with year {year} in file")

        # Check code duplicated in Database (same code and year)
        if (code.lower(), year) in existing_code_year:
            errors.append(f"Employee code {code} with year {year} already exists in database")

        # Process competency fields - handle NaN/empty values properly
        data = {}
        for k in df.columns:
            if k not in required_cols and not str(k).startswith("_"):
                val = row.get(k)
                # Check if value is NaN or empty string
                if pd.isna(val) or (isinstance(val, str) and val.strip() == ""):
                    data[k] = None
                else:
                    data[k] = safe_float(val)

        # Core vs New competency lists
        core_fields = [
            "communication", "continuous_learning", "critical_thinking",
            "data_analysis", "digital_literacy", "problem_solving"
        ]
        core_req_fields = [
            "communication_req", "continuous_learning_req", "critical_thinking_req",
            "data_analysis_req", "digital_literacy_req", "problem_solving_req"
        ]
        
        # Premium competencies (only for non-Officer/Senior)
        premium_fields = ["strategic_thinking", "talent_management", "teamwork_leadership"]
        premium_req_fields = ["strategic_thinking_req", "talent_management_req", "teamwork_leadership_req"]
        
        # Validate forbid inputing competency premium for Officer/Senior
        if title in ["Officer", "Senior"]:
            for f in premium_fields + premium_req_fields:
                val = row.get(f)
                if pd.notna(val) and str(val).strip() != "":
                    errors.append(f"{title} not allowed to fill {f}")
                # Set to None for Officer/Senior
                data[f] = None
        else:
            # For non-Officer/Senior, premium fields are part of core
            core_fields += premium_fields
            core_req_fields += premium_req_fields

        new_fields = ["creative_thinking", "resilience", "ai_bigdata", "analytical_thinking"]
        new_req_fields = ["creative_thinking_req", "resilience_req", "ai_bigdata_req", "analytical_thinking_req"]

        # 1) Core competencies must NOT be null (except premium for Officer/Senior which are already set to None)
        # Ensure all core fields are in data dict (even if column doesn't exist in Excel)
        for key in core_fields + core_req_fields:
            if key not in data:
                # Column doesn't exist in Excel, treat as missing
                data[key] = None
            val = data.get(key)
            if val is None:
                errors.append(f"Missing value for {key} (core competency)")

        # 2) Range check 1.0–5.0 for all non-null numeric fields (core & new)
        for key, val in data.items():
            if val is not None and (val < 1.0 or val > 5.0):
                errors.append(f"Invalid value {val} for {key}")

        # Error --> Skip record
        if errors:
            skipped_details.append({
                "row": idx + 2,
                "code": code,
                "full_name": full_name,
                "reason": "; ".join(errors)
            })
            rows_with_errors.append(row)
            continue

        # Valid -> append to valid_rows list
        valid_rows.append({
            "year": row.get("year"),
            "code": code,
            "full_name": full_name,
            "title": title,
            "department": row.get("department"),
            "division": row.get("division"),
            **data
        })
        success += 1

    # Clean up temporary column
    df.drop("_code_year", axis=1, inplace=True, errors="ignore")
    conn.close()

    if rows_with_errors:
        df_errors = pd.DataFrame(rows_with_errors)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        df_errors.to_excel(tmp.name, index=False)
        error_file_path = tmp.name
    else:
        error_file_path = None

    # Saved session (no insert)
    session["upload_summary"] = {
        "filename": file.filename,
        "success": success,
        "skipped_count": len(skipped_details),
        "skipped_details": skipped_details,
        "valid_rows": valid_rows,
        "time": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "error_file": error_file_path
    }

    return redirect(url_for("additional_info"))

# --- View detail employee ---
@app.route("/detail/<int:emp_id>")
def detail(emp_id):
    conn = get_connection()
    c = conn.cursor()
    table_name = "public.employee" if not isinstance(conn, sqlite3.Connection) else "employee"
    query = f"SELECT * FROM {table_name} WHERE id = %s" if not isinstance(conn, sqlite3.Connection) else f"SELECT * FROM {table_name} WHERE id = ?"
    c.execute(query, (emp_id,))
    row = c.fetchone()
    columns = [desc[0] for desc in c.description]
    conn.close()

    if not row:
        return "Employee not found", 404

    employee = dict(zip(columns, row))
    return render_template("detail.html", employee=employee)


# --- Delete Employee ---
@app.route("/delete-selected", methods=["POST"])
def delete_selected():
    ids = request.form.getlist("selected_ids")
    if not ids:
        flash("No items selected.", "warning")
        return redirect(url_for("employees"))

    ids = tuple(int(i) for i in ids)
    conn = get_connection()
    c = conn.cursor()
    table_name = "public.employee" if not isinstance(conn, sqlite3.Connection) else "employee"
    placeholders = ",".join(["?"] * len(ids)) if isinstance(conn, sqlite3.Connection) else ",".join(["%s"] * len(ids))

    try:
        # 1. Xóa bản ghi
        query = f"DELETE FROM {table_name} WHERE id IN ({placeholders})"
        c.execute(query, ids)
        conn.commit()

        # 2. Cập nhật lại phân loại cho toàn bộ dữ liệu còn lại
        core_keys = ["communication", "continuous_learning", "critical_thinking",
                     "data_analysis", "digital_literacy", "problem_solving",
                     "strategic_thinking", "talent_management", "teamwork_leadership"]
        core_req_keys = ["communication_req", "continuous_learning_req", "critical_thinking_req",
                         "data_analysis_req", "digital_literacy_req", "problem_solving_req",
                         "strategic_thinking_req", "talent_management_req", "teamwork_leadership_req"]

        new_keys = ["creative_thinking", "resilience", "ai_bigdata", "analytical_thinking"]
        new_req_keys = ["creative_thinking_req", "resilience_req", "ai_bigdata_req", "analytical_thinking_req"]

        update_classification_for_all(conn, table_name, core_keys, core_req_keys, "classification_core")
        update_classification_for_all(conn, table_name, new_keys, new_req_keys, "classification_new")

        flash(f"Deleted {len(ids)} record(s) and updated classification successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error deleting: {e}", "danger")
    finally:
        c.close()
        conn.close()

    return redirect(url_for("employees"))


# --- Export Excel ---
@app.route("/export")
def export_data():
    conn = get_connection()
    table_name = "public.employee" if not isinstance(conn, sqlite3.Connection) else "employee"
    df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY id DESC", conn)
    conn.close()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    df.to_excel(tmp.name, index=False)
    tmp.seek(0)

    return send_file(tmp.name, as_attachment=True, download_name="employee_data.xlsx")

# --- Download Excel Template ---
@app.route("/download-template")
def download_template():
    file_path = os.path.join(app.root_path, "static", "employee_template.xlsx")
    return send_file(file_path, as_attachment=True)


# --- API endpoint ---
@app.route("/api/employees")
def api_employees():
    conn = get_connection()
    c = conn.cursor()
    table_name = "public.employee" if not isinstance(conn, sqlite3.Connection) else "employee"
    c.execute(f"SELECT * FROM {table_name} ORDER BY id DESC")
    columns = [desc[0] for desc in c.description]
    data = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return jsonify(data)

@app.route("/additional-info")
def additional_info():
    summary = session.get("upload_summary")
    if not summary:
        flash("Please upload a file before accessing this page.", "warning")
        return redirect(url_for("index"))

    preview = summary.get("valid_rows", [])
    summary["preview"] = preview
    return render_template("extra_info.html", summary=summary)

@app.route("/download-skipped")
def download_skipped():
    summary = session.get("upload_summary")
    if not summary or not summary.get("error_file"):
        flash("No skipped records to download.", "warning")
        return redirect(url_for("additional_info"))

    return send_file(summary["error_file"], as_attachment=True)

@app.route("/extra-info", methods=["POST"])
def extra_info():
    summary = session.get("upload_summary")
    if not summary:
        flash("Session expired, please upload again.", "warning")
        return redirect(url_for("index"))

    handler = request.form.get("handler")
    note = request.form.get("note")

    valid_rows = summary.get("valid_rows", [])
    conn = get_connection()
    c = conn.cursor()
    table_name = "public.employee" if not isinstance(conn, sqlite3.Connection) else "employee"
    placeholders = get_placeholder(conn, 34)

    all_fields = [
        "communication", "continuous_learning", "critical_thinking", "data_analysis",
        "digital_literacy", "problem_solving", "strategic_thinking", "talent_management",
        "teamwork_leadership", "communication_req", "continuous_learning_req",
        "critical_thinking_req", "data_analysis_req", "digital_literacy_req",
        "problem_solving_req", "strategic_thinking_req", "talent_management_req",
        "teamwork_leadership_req", "creative_thinking", "resilience", "ai_bigdata",
        "analytical_thinking", "creative_thinking_req", "resilience_req", "ai_bigdata_req",
        "analytical_thinking_req"
    ]

    # === 1. Insert dữ liệu (classification để tạm Pending) ===
    for row in valid_rows:
        c.execute(f"""
            INSERT INTO {table_name} (
                year, code, full_name, title, department, division,
                {", ".join(all_fields)},
                classification_core, classification_new
            ) VALUES ({placeholders})
        """, (
            row["year"], row["code"], row["full_name"], row["title"],
            row["department"], row["division"],
            *[row.get(k) for k in all_fields],
            "Pending", "Pending"
        ))

    # === 2. Log upload ===
    if isinstance(conn, sqlite3.Connection):
        c.execute("""
            CREATE TABLE IF NOT EXISTS upload_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT, handler TEXT, note TEXT,
                uploaded_records INTEGER, skipped_records INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS upload_log (
                id SERIAL PRIMARY KEY,
                filename TEXT, handler TEXT, note TEXT,
                uploaded_records INTEGER, skipped_records INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    log_placeholders = get_placeholder(conn, 5)
    c.execute(f"""
        INSERT INTO upload_log (filename, handler, note, uploaded_records, skipped_records)
        VALUES ({log_placeholders})
    """, (
        summary["filename"], handler, note,
        summary["success"], summary["skipped_count"]
    ))

    # === 3. Re-classify toàn bộ dữ liệu trong DB ===
    core_keys = ["communication", "continuous_learning", "critical_thinking",
                 "data_analysis", "digital_literacy", "problem_solving",
                 "strategic_thinking", "talent_management", "teamwork_leadership"]

    core_req_keys = ["communication_req", "continuous_learning_req", "critical_thinking_req",
                     "data_analysis_req", "digital_literacy_req", "problem_solving_req",
                     "strategic_thinking_req", "talent_management_req", "teamwork_leadership_req"]

    new_keys = ["creative_thinking", "resilience", "ai_bigdata", "analytical_thinking"]
    new_req_keys = ["creative_thinking_req", "resilience_req", "ai_bigdata_req", "analytical_thinking_req"]

    update_classification_for_all(conn, table_name, core_keys, core_req_keys, "classification_core")
    update_classification_for_all(conn, table_name, new_keys, new_req_keys, "classification_new")

    conn.commit()
    conn.close()

    flash("Upload saved and classifications updated successfully!", "success")
    session.pop("upload_summary", None)
    return redirect(url_for("employees"))

@app.route("/save-form", methods=["POST"])
def save_form():
    session["form_data"] = request.form.to_dict()
    return ("", 204)

# MAIN ENTRY
if __name__ == "__main__":
    # init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
