‎
Original file line number	Diff line number	Diff line change
@@ -1,220 +1,361 @@
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
import bcrypt
from datetime import date
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
app = Flask(__name__)
app.config['SECRET_KEY'] = 'felixcollege2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/database.db'  # CORRECT PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)
# === MODELS ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    class_name = db.Column(db.String(10))
    is_form_teacher = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    def is_authenticated(self): return True
    def is_active(self): return self.is_active
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)
class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    subject = db.Column(db.String(50))
    ca1 = db.Column(db.Integer)
    ca2 = db.Column(db.Integer)
    exam = db.Column(db.Integer)
    total = db.Column(db.Integer)
    grade = db.Column(db.String(5))
    term = db.Column(db.String(20))
    session = db.Column(db.String(20))
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    class_name = db.Column(db.String(10))
    date = db.Column(db.Date)
    status = db.Column(db.String(10))
    marked_by = db.Column(db.Integer, db.ForeignKey('user.id'))
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
# === CREATE DATABASE + superadmin ON EVERY START ===
def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='superadmin').first():
            pwd = bcrypt.hashpw('superpass123'.encode(), bcrypt.gensalt()).decode()
            db.session.add(User(username='superadmin', password=pwd, role='superadmin'))
            teacher_pwd = bcrypt.hashpw('teacher123'.encode(), bcrypt.gensalt()).decode()
            classes = ['JSS1', 'JSS2', 'JSS3', 'SSS1', 'SSS2', 'SSS3']
            for cls in classes:
                db.session.add(User(username=f'formteacher_{cls.lower()}', password=teacher_pwd, role='teacher', class_name=cls, is_form_teacher=True))
            student_pwd = bcrypt.hashpw('123'.encode(), bcrypt.gensalt()).decode()
            for i in range(50):
                class_name = classes[i % len(classes)]
                db.session.add(User(username=f'student_{i+1}_{class_name.lower()}', password=student_pwd, role='student', class_name=class_name))
            db.session.commit()
# === CALL init_db() ON EVERY START ===
init_db()  # THIS LINE IS CRITICAL
# === ROUTES ===
@app.route('/')
def home():
    return redirect(url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode(), user.password.encode()):
            login_user(user)
            if user.role == 'superadmin':
                return redirect(url_for('admin_dash'))
            elif user.role == 'student':
                return redirect(url_for('student_dash'))
            else:
                return redirect(url_for('teacher_dash'))
        flash('Wrong username or password!')
    return render_template('login.html')
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))
@app.route('/student')
@login_required
def student_dash():
    if current_user.role != 'student': return redirect(url_for('login'))
    results = Result.query.filter_by(student_id=current_user.id).all()
    return render_template('student_dashboard.html', results=results, name=current_user.username)
@app.route('/teacher')
@login_required
def teacher_dash():
    if current_user.role != 'teacher': return redirect(url_for('login'))
    students = User.query.filter_by(class_name=current_user.class_name, role='student').all()
    return render_template('teacher_dashboard.html', students=students)
@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    if not (current_user.is_form_teacher and current_user.role == 'teacher'):
        flash('Only Form Teachers!')
        return redirect(url_for('teacher_dash'))
    students = User.query.filter_by(class_name=current_user.class_name, role='student').all()
    today = date.today()
    if request.method == 'POST':
        for s in students:
            status = request.form.get(f'status_{s.id}')
            if status:
                rec = Attendance.query.filter_by(student_id=s.id, date=today).first()
                if rec:
                    rec.status = status
                else:
                    db.session.add(Attendance(student_id=s.id, class_name=s.class_name, date=today, status=status, marked_by=current_user.id))
        db.session.commit()
        flash('Attendance saved!')
    records = Attendance.query.filter_by(date=today, class_name=current_user.class_name).all()
    att_dict = {r.student_id: r.status for r in records}
    return render_template('attendance.html', students=students, att_dict=att_dict, today=today)
@app.route('/upload_result', methods=['GET', 'POST'])
@login_required
def upload_result():
    if current_user.role != 'teacher': return redirect(url_for('login'))
    students = User.query.filter_by(class_name=current_user.class_name, role='student').all()
    if request.method == 'POST':
        sid = request.form['student_id']
        subject = request.form['subject']
        ca1 = int(request.form.get('ca1', 0))
        ca2 = int(request.form.get('ca2', 0))
        exam = int(request.form.get('exam', 0))
        total = ca1 + ca2 + exam
        grade = 'A' if total >= 70 else 'B' if total >= 60 else 'C' if total >= 50 else 'D' if total >= 40 else 'F'
        term = request.form['term']
        session = request.form['session']
        db.session.add(Result(student_id=sid, subject=subject, ca1=ca1, ca2=ca2, exam=exam, total=total, grade=grade, term=term, session=session))
        db.session.commit()
        flash('Result saved!')
    return render_template('upload_result.html', students=students)
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dash():
    if current_user.username != 'superadmin':
        flash('Only Super Admin!')
        return redirect(url_for('teacher_dash' if current_user.role == 'teacher' else 'student_dash'))
    users = User.query.all()
    if request.method == 'POST' and 'add_student' in request.form:
        username = request.form['student_username']
        pwd = bcrypt.hashpw(request.form['student_password'].encode(), bcrypt.gensalt()).decode()
        class_name = request.form['student_class']
        db.session.add(User(username=username, password=pwd, role='student', class_name=class_name))
        db.session.commit()
        flash('Student added!')
    if request.method == 'POST' and 'add_teacher' in request.form:
        username = request.form['teacher_username']
        pwd = bcrypt.hashpw(request.form['teacher_password'].encode(), bcrypt.gensalt()).decode()
        class_name = request.form['teacher_class']
        is_form = 'form_teacher' in request.form
        db.session.add(User(username=username, password=pwd, role='teacher', class_name=class_name, is_form_teacher=is_form))
        db.session.commit()
        flash('Teacher added!')
    return render_template('admin_dashboard.html', users=users)
@app.route('/print_result/<int:student_id>')
@login_required
def print_result(student_id):
    student = User.query.get(student_id)
    if not student or student.role != 'student':
        flash('Student not found!')
        return redirect(url_for('student_dash'))
    results = Result.query.filter_by(student_id=student_id).all()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    story.append(Paragraph("FELIX COLLEGE - RESULT SHEET", styles['Title']))
    story.append(Spacer(1, 12))
    data = [['Student:', student.username], ['Class:', student.class_name]]
    table = Table(data)
    table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
    story.append(table)
    story.append(Spacer(1, 12))
    if results:
        headers = ['Subject', 'CA1', 'CA2', 'Exam', 'Total', 'Grade', 'Term']
        result_data = [headers] + [[r.subject, r.ca1, r.ca2, r.exam, r.total, r.grade, r.term] for r in results]
        result_table = Table(result_data)
        result_table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
        story.append(result_table)
    else:
        story.append(Paragraph("No results.", styles['Normal']))
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'{student.username}_results.pdf', mimetype='application/pdf')
# === NO if __name__ == '__main__' — RENDER DOESN'T RUN IT ===
 2))
  Downloading typing_extensions-4.15.0-py3-none-any.whl.metadata (3.3 kB)
Downloading flask-3.1.2-py3-none-any.whl (103 kB)
Downloading flask_sqlalchemy-3.1.1-py3-none-any.whl (25 kB)
Downloading bcrypt-5.0.0-cp39-abi3-manylinux_2_34_x86_64.whl (278 kB)
Downloading reportlab-4.0.4-py3-none-any.whl (1.9 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.9/1.9 MB 47.7 MB/s eta 0:00:00
Downloading gunicorn-21.2.0-py3-none-any.whl (80 kB)
Downloading Flask_Login-0.6.3-py3-none-any.whl (17 kB)
Downloading blinker-1.9.0-py3-none-any.whl (8.5 kB)
Downloading click-8.3.0-py3-none-any.whl (107 kB)
Downloading itsdangerous-2.2.0-py3-none-any.whl (16 kB)
Downloading jinja2-3.1.6-py3-none-any.whl (134 kB)
Downloading markupsafe-3.0.3-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (22 kB)
Downloading pillow-12.0.0-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (7.0 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 7.0/7.0 MB 189.3 MB/s eta 0:00:00
Downloading sqlalchemy-2.0.44-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (3.3 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3.3/3.3 MB 103.7 MB/s eta 0:00:00
Downloading greenlet-3.2.4-cp313-cp313-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl (610 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 610.5/610.5 kB 47.5 MB/s eta 0:00:00
Downloading typing_extensions-4.15.0-py3-none-any.whl (44 kB)
Downloading werkzeug-3.1.3-py3-none-any.whl (224 kB)
Downloading packaging-25.0-py3-none-any.whl (66 kB)
Installing collected packages: typing-extensions, pillow, packaging, markupsafe, itsdangerous, greenlet, click, blinker, bcrypt, werkzeug, sqlalchemy, reportlab, jinja2, gunicorn, Flask, Flask-SQLAlchemy, Flask-Login
Successfully installed Flask-3.1.2 Flask-Login-0.6.3 Flask-SQLAlchemy-3.1.1 bcrypt-5.0.0 blinker-1.9.0 click-8.3.0 greenlet-3.2.4 gunicorn-21.2.0 itsdangerous-2.2.0 jinja2-3.1.6 markupsafe-3.0.3 packaging-25.0 pillow-12.0.0 reportlab-4.0.4 sqlalchemy-2.0.44 typing-extensions-4.15.0 werkzeug-3.1.3
[notice] A new release of pip is available: 25.1.1 -> 25.3
[notice] To update, run: pip install --upgrade pip
==> Uploading build...
==> Uploaded in 11.0s. Compression took 3.0s
==> Build successful 🎉
==> Deploying...
==> Running 'gunicorn app:app'
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 143, in __init__
    self._dbapi_connection = engine.raw_connection()
                             ~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3301, in raw_connection
    return self.pool.connect()
           ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 447, in connect
    return _ConnectionFairy._checkout(self)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 1264, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 711, in checkout
    rec = pool._do_get()
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/impl.py", line 177, in _do_get
    with util.safe_reraise():
         ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/util/langhelpers.py", line 224, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/impl.py", line 175, in _do_get
    return self._create_connection()
           ~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 388, in _create_connection
    return _ConnectionRecord(self)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 673, in __init__
    self.__connect()
    ~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 899, in __connect
    with util.safe_reraise():
         ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/util/langhelpers.py", line 224, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 895, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/create.py", line 661, in connect
    return dialect.connect(*cargs, **cparams)
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/default.py", line 629, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
sqlite3.OperationalError: unable to open database file
The above exception was the direct cause of the following exception:
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/bin/gunicorn", line 8, in <module>
    sys.exit(run())
             ~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 67, in run
    WSGIApplication("%(prog)s [OPTIONS] [APP_MODULE]").run()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/base.py", line 236, in run
    super().run()
    ~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/base.py", line 72, in run
    Arbiter(self).run()
    ~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/arbiter.py", line 58, in __init__
    self.setup(app)
    ~~~~~~~~~~^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/arbiter.py", line 118, in setup
    self.app.wsgi()
    ~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/base.py", line 67, in wsgi
    self.callable = self.load()
                    ~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 58, in load
    return self.load_wsgiapp()
           ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 48, in load_wsgiapp
    return util.import_app(self.app_uri)
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/util.py", line 371, in import_app
    mod = importlib.import_module(module)
  File "/opt/render/project/python/Python-3.13.4/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1026, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/opt/render/project/src/app.py", line 79, in <module>
    init_db()  # THIS LINE IS CRITICAL
    ~~~~~~~^^
  File "/opt/render/project/src/app.py", line 64, in init_db
    db.create_all()
    ~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/flask_sqlalchemy/extension.py", line 900, in create_all
    self._call_for_binds(bind_key, "create_all")
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/flask_sqlalchemy/extension.py", line 881, in _call_for_binds
    getattr(metadata, op_name)(bind=engine)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/sql/schema.py", line 5928, in create_all
    bind._run_ddl_visitor(
    ~~~~~~~~~~~~~~~~~~~~~^
        ddl.SchemaGenerator, self, checkfirst=checkfirst, tables=tables
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3251, in _run_ddl_visitor
    with self.begin() as conn:
         ~~~~~~~~~~^^
  File "/opt/render/project/python/Python-3.13.4/lib/python3.13/contextlib.py", line 141, in __enter__
    return next(self.gen)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3241, in begin
    with self.connect() as conn:
         ~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3277, in connect
    return self._connection_cls(self)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 145, in __init__
    Connection._handle_dbapi_exception_noconnection(
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        err, dialect, engine
        ^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 2440, in _handle_dbapi_exception_noconnection
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 143, in __init__
    self._dbapi_connection = engine.raw_connection()
                             ~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3301, in raw_connection
    return self.pool.connect()
           ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 447, in connect
    return _ConnectionFairy._checkout(self)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 1264, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 711, in checkout
    rec = pool._do_get()
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/impl.py", line 177, in _do_get
    with util.safe_reraise():
         ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/util/langhelpers.py", line 224, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/impl.py", line 175, in _do_get
    return self._create_connection()
           ~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 388, in _create_connection
    return _ConnectionRecord(self)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 673, in __init__
    self.__connect()
    ~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 899, in __connect
    with util.safe_reraise():
         ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/util/langhelpers.py", line 224, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 895, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/create.py", line 661, in connect
    return dialect.connect(*cargs, **cparams)
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/default.py", line 629, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
==> Exited with status 1
==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
==> Running 'gunicorn app:app'
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 143, in __init__
    self._dbapi_connection = engine.raw_connection()
                             ~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3301, in raw_connection
    return self.pool.connect()
           ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 447, in connect
    return _ConnectionFairy._checkout(self)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 1264, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 711, in checkout
    rec = pool._do_get()
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/impl.py", line 177, in _do_get
    with util.safe_reraise():
         ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/util/langhelpers.py", line 224, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/impl.py", line 175, in _do_get
    return self._create_connection()
           ~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 388, in _create_connection
    return _ConnectionRecord(self)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 673, in __init__
    self.__connect()
    ~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 899, in __connect
    with util.safe_reraise():
         ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/util/langhelpers.py", line 224, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 895, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/create.py", line 661, in connect
    return dialect.connect(*cargs, **cparams)
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/default.py", line 629, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
sqlite3.OperationalError: unable to open database file
The above exception was the direct cause of the following exception:
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/bin/gunicorn", line 8, in <module>
    sys.exit(run())
             ~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 67, in run
    WSGIApplication("%(prog)s [OPTIONS] [APP_MODULE]").run()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/base.py", line 236, in run
    super().run()
    ~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/base.py", line 72, in run
    Arbiter(self).run()
    ~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/arbiter.py", line 58, in __init__
    self.setup(app)
    ~~~~~~~~~~^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/arbiter.py", line 118, in setup
    self.app.wsgi()
    ~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/base.py", line 67, in wsgi
    self.callable = self.load()
                    ~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 58, in load
    return self.load_wsgiapp()
           ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/app/wsgiapp.py", line 48, in load_wsgiapp
    return util.import_app(self.app_uri)
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/gunicorn/util.py", line 371, in import_app
    mod = importlib.import_module(module)
  File "/opt/render/project/python/Python-3.13.4/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1026, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/opt/render/project/src/app.py", line 79, in <module>
    init_db()  # THIS LINE IS CRITICAL
    ~~~~~~~^^
  File "/opt/render/project/src/app.py", line 64, in init_db
    db.create_all()
    ~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/flask_sqlalchemy/extension.py", line 900, in create_all
    self._call_for_binds(bind_key, "create_all")
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/flask_sqlalchemy/extension.py", line 881, in _call_for_binds
    getattr(metadata, op_name)(bind=engine)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/sql/schema.py", line 5928, in create_all
    bind._run_ddl_visitor(
    ~~~~~~~~~~~~~~~~~~~~~^
        ddl.SchemaGenerator, self, checkfirst=checkfirst, tables=tables
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3251, in _run_ddl_visitor
    with self.begin() as conn:
         ~~~~~~~~~~^^
  File "/opt/render/project/python/Python-3.13.4/lib/python3.13/contextlib.py", line 141, in __enter__
    return next(self.gen)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3241, in begin
    with self.connect() as conn:
         ~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3277, in connect
    return self._connection_cls(self)
           ~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 145, in __init__
    Connection._handle_dbapi_exception_noconnection(
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        err, dialect, engine
        ^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 2440, in _handle_dbapi_exception_noconnection
    raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 143, in __init__
    self._dbapi_connection = engine.raw_connection()
                             ~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 3301, in raw_connection
    return self.pool.connect()
           ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 447, in connect
    return _ConnectionFairy._checkout(self)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 1264, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 711, in checkout
    rec = pool._do_get()
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/impl.py", line 177, in _do_get
    with util.safe_reraise():
         ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/util/langhelpers.py", line 224, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/impl.py", line 175, in _do_get
    return self._create_connection()
           ~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 388, in _create_connection
    return _ConnectionRecord(self)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 673, in __init__
    self.__connect()
    ~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 899, in __connect
    with util.safe_reraise():
         ~~~~~~~~~~~~~~~~~^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/util/langhelpers.py", line 224, in __exit__
    raise exc_value.with_traceback(exc_tb)
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/pool/base.py", line 895, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
                                         ~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/create.py", line 661, in connect
    return dialect.connect(*cargs, **cparams)
           ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.13/site-packages/sqlalchemy/engine/default.py", line 629, in connect
    return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
           ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
