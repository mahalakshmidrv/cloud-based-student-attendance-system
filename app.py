import os, sqlite3, csv, io
from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DATABASE_PATH", os.path.join(BASE, "attendance.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")

def connect():
    os.makedirs(os.path.dirname(os.path.abspath(DB)), exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS teachers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY, roll TEXT UNIQUE NOT NULL, name TEXT NOT NULL, class_name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE, day TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('Present','Absent','Late')), marked_by INTEGER REFERENCES teachers(id), UNIQUE(student_id,day));
        """)
init_db()

def auth(fn):
    @wraps(fn)
    def inner(*a, **kw):
        if not session.get("teacher_id"):
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return inner

@app.route("/")
def home():
    return redirect(url_for("dashboard" if session.get("teacher_id") else "login"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name=request.form.get("name","").strip()
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        if not name or not email or len(password)<8:
            flash("Enter all details and use a password of at least 8 characters.","error")
        else:
            try:
                with connect() as c:
                    c.execute("INSERT INTO teachers(name,email,password) VALUES(?,?,?)",(name,email,generate_password_hash(password)))
                flash("Account created. Please sign in.","success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.","error")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        with connect() as c:
            user=c.execute("SELECT * FROM teachers WHERE email=?",(request.form.get("email","").strip().lower(),)).fetchone()
        if user and check_password_hash(user["password"],request.form.get("password","")):
            session.clear(); session["teacher_id"]=user["id"]; session["teacher_name"]=user["name"]
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.","error")
    return render_template("login.html")

@app.post("/logout")
@auth
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@auth
def dashboard():
    day=request.args.get("day",date.today().isoformat())
    try: datetime.strptime(day,"%Y-%m-%d")
    except ValueError: day=date.today().isoformat()
    with connect() as c:
        students=c.execute("""SELECT s.*, a.status FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.day=? ORDER BY s.class_name,s.roll""",(day,)).fetchall()
        total=c.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        counts={r["status"]:r["n"] for r in c.execute("SELECT status,COUNT(*) n FROM attendance WHERE day=? GROUP BY status",(day,))}
    return render_template("dashboard.html",students=students,day=day,total=total,present=counts.get("Present",0),absent=counts.get("Absent",0),late=counts.get("Late",0))

@app.route("/students",methods=["GET","POST"])
@auth
def students_page():
    if request.method=="POST":
        roll=request.form.get("roll","").strip()
        name=request.form.get("name","").strip()
        cls=request.form.get("class_name","").strip()
        if not all([roll,name,cls]): flash("Please complete every field.","error")
        else:
            try:
                with connect() as c: c.execute("INSERT INTO students(roll,name,class_name) VALUES(?,?,?)",(roll,name,cls))
                flash("Student added.","success"); return redirect(url_for("students_page"))
            except sqlite3.IntegrityError: flash("Roll number already exists.","error")
    with connect() as c: rows=c.execute("SELECT * FROM students ORDER BY class_name,roll").fetchall()
    return render_template("students.html",students=rows)

@app.post("/students/<int:sid>/delete")
@auth
def delete_student(sid):
    with connect() as c: c.execute("DELETE FROM students WHERE id=?",(sid,))
    flash("Student deleted.","success")
    return redirect(url_for("students_page"))

@app.post("/attendance")
@auth
def save_attendance():
    day=request.form.get("day",date.today().isoformat())
    try: datetime.strptime(day,"%Y-%m-%d")
    except ValueError: flash("Invalid date.","error"); return redirect(url_for("dashboard"))
    with connect() as c:
        ids=[r["id"] for r in c.execute("SELECT id FROM students")]
        for sid in ids:
            status=request.form.get("status_"+str(sid))
            if status in ("Present","Absent","Late"):
                c.execute("""INSERT INTO attendance(student_id,day,status,marked_by) VALUES(?,?,?,?)
                ON CONFLICT(student_id,day) DO UPDATE SET status=excluded.status,marked_by=excluded.marked_by""",(sid,day,status,session["teacher_id"]))
    flash("Attendance saved.","success")
    return redirect(url_for("dashboard",day=day))

@app.route("/reports")
@auth
def reports():
    with connect() as c:
        rows=c.execute("""SELECT s.roll,s.name,s.class_name,
        SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) present,
        SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) absent,
        SUM(CASE WHEN a.status='Late' THEN 1 ELSE 0 END) late,COUNT(a.id) marked
        FROM students s LEFT JOIN attendance a ON a.student_id=s.id
        GROUP BY s.id ORDER BY s.class_name,s.roll""").fetchall()
    return render_template("reports.html",students=rows)

@app.route("/reports.csv")
@auth
def csv_report():
    with connect() as c:
        rows=c.execute("""SELECT s.roll,s.name,s.class_name,a.day,a.status FROM attendance a
        JOIN students s ON s.id=a.student_id ORDER BY a.day DESC,s.class_name,s.roll""").fetchall()
    out=io.StringIO(); w=csv.writer(out); w.writerow(["Roll Number","Student Name","Class","Date","Status"])
    for r in rows: w.writerow([r["roll"],r["name"],r["class_name"],r["day"],r["status"]])
    return Response(out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=attendance-report.csv"})

@app.get("/health")
def health(): return {"status":"ok"}

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)
