import os, csv, io, secrets, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(APP_DIR, 'total_grace.db'))
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'CHANGE-THIS-BEFORE-DEPLOYING-' + secrets.token_hex(16))
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=2*1024*1024)

SECTIONS = ['Primary', 'Secondary']
SCORE_LIMITS = {'Primary': (40, 60), 'Secondary': (30, 70)}
TERMS = ['First Term', 'Second Term', 'Third Term']


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, admission_no TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, section TEXT NOT NULL, class_name TEXT NOT NULL, pin_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, session_name TEXT NOT NULL, term TEXT NOT NULL, subject TEXT NOT NULL, ca REAL NOT NULL DEFAULT 0, exam REAL NOT NULL DEFAULT 0, teacher_remark TEXT DEFAULT '', FOREIGN KEY(student_id) REFERENCES students(id), UNIQUE(student_id, session_name, term, subject));
        CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, session_name TEXT NOT NULL, term TEXT NOT NULL, class_teacher TEXT DEFAULT '', principal TEXT DEFAULT '', FOREIGN KEY(student_id) REFERENCES students(id), UNIQUE(student_id, session_name, term));
        ''')
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        password = os.environ.get('ADMIN_PASSWORD', 'ChangeMe123!')
        row = con.execute('SELECT id FROM admins WHERE username=?', (username,)).fetchone()
        if not row:
            con.execute('INSERT INTO admins(username,password_hash) VALUES(?,?)', (username, generate_password_hash(password)))


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(24)
    return session['csrf']
app.jinja_env.globals['csrf_token'] = csrf_token

@app.before_request
def csrf_protect():
    if request.method == 'POST':
        sent = request.form.get('csrf_token', '')
        if not sent or not secrets.compare_digest(sent, session.get('csrf', '')):
            return 'Invalid form token. Please go back and try again.', 400


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('admin_login'))
        return fn(*args, **kwargs)
    return wrapper


def grade(total):
    if total >= 75: return 'A'
    if total >= 65: return 'B'
    if total >= 50: return 'C'
    if total >= 40: return 'D'
    return 'F'

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/check-result', methods=['GET','POST'])
def check_result():
    result_data = None
    if request.method == 'POST':
        admission = request.form.get('admission_no','').strip()
        pin = request.form.get('pin','').strip()
        session_name = request.form.get('session_name','').strip()
        term = request.form.get('term','').strip()
        with db() as con:
            student = con.execute('SELECT * FROM students WHERE admission_no=?', (admission,)).fetchone()
            if student and check_password_hash(student['pin_hash'], pin):
                rows = con.execute('SELECT * FROM results WHERE student_id=? AND session_name=? AND term=? ORDER BY subject', (student['id'], session_name, term)).fetchall()
                comment = con.execute('SELECT * FROM comments WHERE student_id=? AND session_name=? AND term=?', (student['id'], session_name, term)).fetchone()
                if rows:
                    subjects = []
                    ca_max, exam_max = SCORE_LIMITS[student['section']]
                    for r in rows:
                        total = float(r['ca']) + float(r['exam'])
                        subjects.append({**dict(r), 'total': total, 'grade': grade(total)})
                    result_data = {'student': student, 'subjects': subjects, 'total': sum(x['total'] for x in subjects), 'average': sum(x['total'] for x in subjects)/len(subjects), 'comment': comment, 'session_name': session_name, 'term': term, 'ca_max': ca_max, 'exam_max': exam_max}
                else:
                    flash('No result was found for the selected session and term.', 'warning')
            else:
                flash('Admission number or PIN is incorrect.', 'error')
    return render_template('check_result.html', result=result_data, terms=TERMS)

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        with db() as con:
            admin = con.execute('SELECT * FROM admins WHERE username=?', (username,)).fetchone()
        if admin and check_password_hash(admin['password_hash'], password):
            session.clear(); session['admin_id'] = admin['id']; session['csrf'] = secrets.token_urlsafe(24)
            return redirect(url_for('admin_dashboard'))
        flash('Login details are incorrect.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    session.clear(); return redirect(url_for('home'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    with db() as con:
        students = con.execute('SELECT * FROM students ORDER BY section,class_name,full_name').fetchall()
        result_count = con.execute('SELECT COUNT(*) n FROM results').fetchone()['n']
    return render_template('admin.html', students=students, result_count=result_count, sections=SECTIONS)

@app.route('/admin/student', methods=['POST'])
@admin_required
def add_student():
    admission = request.form.get('admission_no','').strip()
    name = request.form.get('full_name','').strip()
    section = request.form.get('section','')
    class_name = request.form.get('class_name','').strip()
    pin = request.form.get('pin','').strip()
    if not all([admission,name,class_name,pin]) or section not in SECTIONS:
        flash('Complete all student fields.', 'error'); return redirect(url_for('admin_dashboard'))
    try:
        with db() as con:
            con.execute('INSERT INTO students(admission_no,full_name,section,class_name,pin_hash) VALUES(?,?,?,?,?)', (admission,name,section,class_name,generate_password_hash(pin)))
        flash('Student added successfully. Give the PIN to the parent/guardian securely.', 'success')
    except sqlite3.IntegrityError:
        flash('That admission number already exists.', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/result', methods=['POST'])
@admin_required
def add_result():
    student_id = request.form.get('student_id','')
    session_name = request.form.get('session_name','').strip()
    term = request.form.get('term','')
    subject = request.form.get('subject','').strip()
    if not all([student_id,session_name,subject]) or term not in TERMS:
        flash('Complete all result fields.', 'error'); return redirect(url_for('admin_dashboard'))
    with db() as con:
        student = con.execute('SELECT section FROM students WHERE id=?', (student_id,)).fetchone()
    if not student or student['section'] not in SCORE_LIMITS:
        flash('Choose a valid Primary or Secondary student.', 'error'); return redirect(url_for('admin_dashboard'))
    ca_max, exam_max = SCORE_LIMITS[student['section']]
    try:
        ca, exam = float(request.form.get('ca','')), float(request.form.get('exam',''))
        if ca < 0 or exam < 0 or ca > ca_max or exam > exam_max: raise ValueError()
    except ValueError:
        flash(f'Enter valid scores: CA must be 0–{ca_max} and exam 0–{exam_max}.', 'error'); return redirect(url_for('admin_dashboard'))
    with db() as con:
        con.execute('''INSERT INTO results(student_id,session_name,term,subject,ca,exam,teacher_remark) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(student_id,session_name,term,subject) DO UPDATE SET ca=excluded.ca, exam=excluded.exam, teacher_remark=excluded.teacher_remark''',
        (student_id,session_name,term,subject,ca,exam,request.form.get('teacher_remark','').strip()))
    flash('Result saved.', 'success'); return redirect(url_for('admin_dashboard'))

@app.route('/admin/comments', methods=['POST'])
@admin_required
def save_comments():
    student_id=request.form.get('student_id',''); session_name=request.form.get('session_name','').strip(); term=request.form.get('term','')
    if not student_id or not session_name or term not in TERMS:
        flash('Complete student, session and term.', 'error'); return redirect(url_for('admin_dashboard'))
    with db() as con:
        con.execute('''INSERT INTO comments(student_id,session_name,term,class_teacher,principal) VALUES(?,?,?,?,?)
        ON CONFLICT(student_id,session_name,term) DO UPDATE SET class_teacher=excluded.class_teacher, principal=excluded.principal''',
        (student_id,session_name,term,request.form.get('class_teacher','').strip(),request.form.get('principal','').strip()))
    flash('Comments saved.', 'success'); return redirect(url_for('admin_dashboard'))

@app.route('/admin/import', methods=['POST'])
@admin_required
def import_csv():
    file=request.files.get('file')
    if not file or not file.filename.lower().endswith('.csv'):
        flash('Choose a CSV file.', 'error'); return redirect(url_for('admin_dashboard'))
    try:
        stream=io.StringIO(file.stream.read().decode('utf-8-sig'))
        reader=csv.DictReader(stream)
        required={'admission_no','full_name','section','class_name','pin','session','term','subject','ca','exam'}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError('CSV headers are missing or incorrect. Download/use the sample CSV format.')
        count=0
        with db() as con:
            for row in reader:
                section=row['section'].strip(); term=row['term'].strip()
                if section not in SECTIONS or term not in TERMS: raise ValueError('Invalid section or term in CSV.')
                if section not in SCORE_LIMITS: raise ValueError('Only Primary and Secondary sections are supported.')
                ca=float(row['ca']); exam=float(row['exam'])
                ca_max, exam_max = SCORE_LIMITS[section]
                if not (0<=ca<=ca_max and 0<=exam<=exam_max):
                    raise ValueError(f'{section} scores must use CA 0–{ca_max} and exam 0–{exam_max}.')
                con.execute('''INSERT INTO students(admission_no,full_name,section,class_name,pin_hash) VALUES(?,?,?,?,?)
                    ON CONFLICT(admission_no) DO UPDATE SET full_name=excluded.full_name,section=excluded.section,class_name=excluded.class_name''',
                    (row['admission_no'].strip(),row['full_name'].strip(),section,row['class_name'].strip(),generate_password_hash(row['pin'].strip())))
                student=con.execute('SELECT id FROM students WHERE admission_no=?',(row['admission_no'].strip(),)).fetchone()
                con.execute('''INSERT INTO results(student_id,session_name,term,subject,ca,exam,teacher_remark) VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(student_id,session_name,term,subject) DO UPDATE SET ca=excluded.ca,exam=excluded.exam,teacher_remark=excluded.teacher_remark''',
                    (student['id'],row['session'].strip(),term,row['subject'].strip(),ca,exam,row.get('teacher_remark','').strip()))
                count+=1
        flash(f'Imported {count} subject-result rows.', 'success')
    except Exception as e:
        flash(f'Import failed: {e}', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/sample.csv')
@admin_required
def sample_csv():
    content='admission_no,full_name,section,class_name,pin,session,term,subject,ca,exam,teacher_remark\nTG001,Sample Student,Primary,Primary 5,482913,2026/2027,First Term,English,32,48,Good effort\n'
    response=make_response(content); response.headers['Content-Disposition']='attachment; filename=total_grace_sample_results.csv'; response.headers['Content-Type']='text/csv'; return response

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    return response

init_db()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)), debug=False)
