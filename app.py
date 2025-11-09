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
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'felixcollege2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tmp/database.db'  # RENDER-FRIENDLY PATH
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

# === INIT DB ON FIRST REQUEST ===
@app.before_first_request
def init_db():
    os.makedirs('/tmp', exist_ok=True)  # /tmp always exists
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