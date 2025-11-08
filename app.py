from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
import bcrypt
from datetime import date, datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

app = Flask(__name__)
app.config['SECRET_KEY'] = 'felixcollege2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# === DATABASE MODELS ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    class_name = db.Column(db.String(10))
    is_form_teacher = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    def is_authenticated(self):
        return True

    def is_active(self):
        return self.is_active

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

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

# === CREATE DEFAULT USERS + 50 STUDENTS ===
def create_users():
    if not User.query.filter_by(username='admin').first():
        pwd = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
        admin = User(username='admin', password=pwd, role='teacher', class_name='JSS1', is_form_teacher=True)
        db.session.add(admin)

        pwd2 = bcrypt.hashpw('123'.encode(), bcrypt.gensalt()).decode()
        student = User(username='jss1_student', password=pwd2, role='student', class_name='JSS1')
        db.session.add(student)

        # Add 50 students across all classes (JSS1-SSS3)
        classes = ['JSS1', 'JSS2', 'JSS3', 'SSS1', 'SSS2', 'SSS3']
        for i in range(50):
            class_name = classes[i % len(classes)]
            username = f'student_{i+1}_{class_name.lower()}'
            user = User(username=username, password=pwd2, role='student', class_name=class_name)
            db.session.add(user)

        # Add some teachers
        teacher_pwd = bcrypt.hashpw('teacher123'.encode(), bcrypt.gensalt()).decode()
        teacher_classes = ['JSS2', 'JSS3', 'SSS1', 'SSS2', 'SSS3']
        for i, cls in enumerate(teacher_classes):
            t = User(username=f'teacher_{cls.lower()}', password=teacher_pwd, role='teacher', class_name=cls, is_form_teacher=True)
            db.session.add(t)

        db.session.commit()

# === ROUTES ===
@app.route('/')
def home():
    return redirect(url_for('login'))

# === REGISTRATION PAGE ===
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.hashpw(request.form['password'].encode(), bcrypt.gensalt()).decode()
        role = request.form['role']
        class_name = request.form.get('class_name', '')
        is_form_teacher = 'form_teacher' in request.form

        if role == 'teacher' and not class_name:
            flash('Teachers must select a class!')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username taken!')
            return render_template('register.html')

        user = User(username=username, password=password, role=role, class_name=class_name, is_form_teacher=is_form_teacher)
        db.session.add(user)
        db.session.commit()
        flash('Registered! Login now.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode(), user.password.encode()):
            login_user(user)
            if user.role == 'student':
                return redirect(url_for('student_dash'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher_dash'))
            else:
                return redirect(url_for('admin_dash'))
        flash('Wrong username or password!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# === STUDENT DASHBOARD ===
@app.route('/student')
@login_required
def student_dash():
    if current_user.role != 'student':
        return redirect(url_for('login'))
    results = Result.query.filter_by(student_id=current_user.id).all()
    return render_template('student_dashboard.html', results=results, name=current_user.username)

# === TEACHER DASHBOARD (UPGRADED WITH ADD LINK) ===
@app.route('/teacher')
@login_required
def teacher_dash():
    if current_user.role != 'teacher':
        return redirect(url_for('login'))
    students = User.query.filter_by(class_name=current_user.class_name, role='student').all()
    return render_template('teacher_dashboard.html', students=students)

# === MARK ATTENDANCE ===
@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    if not current_user.is_form_teacher:
        flash('Only Form Teacher can mark attendance!')
        return redirect(url_for('teacher_dash'))

    students = User.query.filter_by(class_name=current_user.class_name, role='student').all()
    today = date.today()

    if request.method == 'POST':
        for student in students:
            status = request.form.get(f'status_{student.id}')
            if status:
                record = Attendance.query.filter_by(student_id=student.id, date=today).first()
                if record:
                    record.status = status
                else:
                    new_att = Attendance(student_id=student.id, class_name=student.class_name, date=today, status=status, marked_by=current_user.id)
                    db.session.add(new_att)
        db.session.commit()
        flash('Attendance saved!')
        return redirect(url_for('teacher_dash'))

    records = Attendance.query.filter_by(date=today).all()
    att_dict = {r.student_id: r.status for r in records}
    return render_template('attendance.html', students=students, att_dict=att_dict, today=today)

# === UPLOAD RESULT ===
@app.route('/upload_result', methods=['GET', 'POST'])
@login_required
def upload_result():
    if current_user.role != 'teacher':
        return redirect(url_for('login'))

    students = User.query.filter_by(class_name=current_user.class_name, role='student').all()

    if request.method == 'POST':
        sid = request.form['student_id']
        subject = request.form['subject']
        ca1 = int(request.form.get('ca1', 0))
        ca2 = int(request.form.get('ca2', 0))
        exam = int(request.form.get('exam', 0))
        term = request.form['term']
        session = request.form['session']
        total = ca1 + ca2 + exam
        grade = 'A' if total >= 70 else 'B' if total >= 60 else 'C' if total >= 50 else 'D' if total >= 40 else 'F'

        result = Result(student_id=sid, subject=subject, ca1=ca1, ca2=ca2, exam=exam, total=total, grade=grade, term=term, session=session)
        db.session.add(result)
        db.session.commit()
        flash('Result saved!')
        return redirect(url_for('teacher_dash'))

    return render_template('upload_result.html', students=students)

# === ADMIN PANEL (UPGRADED WITH ADD FORMS) ===
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dash():
    if current_user.username != 'admin':
        flash('Only admin can access!')
        return redirect(url_for('login'))

    users = User.query.all()

    # Add Student Form
    if request.method == 'POST' and 'add_student' in request.form:
        username = request.form['student_username']
        password = bcrypt.hashpw(request.form['student_password'].encode(), bcrypt.gensalt()).decode()
        class_name = request.form['student_class']
        student = User(username=username, password=password, role='student', class_name=class_name)
        db.session.add(student)
        db.session.commit()
        flash('Student added!')
        return redirect(url_for('admin_dash'))

    # Add Teacher Form
    if request.method == 'POST' and 'add_teacher' in request.form:
        username = request.form['teacher_username']
        password = bcrypt.hashpw(request.form['teacher_password'].encode(), bcrypt.gensalt()).decode()
        class_name = request.form['teacher_class']
        is_form = 'form_teacher' in request.form
        teacher = User(username=username, password=password, role='teacher', class_name=class_name, is_form_teacher=is_form)
        db.session.add(teacher)
        db.session.commit()
        flash('Teacher added!')
        return redirect(url_for('admin_dash'))

    return render_template('admin_dashboard.html', users=users)

# === PDF PRINT ===
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

    # Title
    title = Paragraph("FELIX COLLEGE - RESULT SHEET", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    # Student Info
    data = [['Student:', student.username], ['Class:', student.class_name]]
    table = Table(data)
    table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.grey),
                               ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
                               ('ALIGN',(0,0),(-1,-1),'CENTER'),
                               ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                               ('FONTSIZE', (0,0), (-1,0), 14),
                               ('BOTTOMPADDING', (0,0), (-1,0), 12),
                               ('BACKGROUND',(0,1),(-1,-1),colors.beige),
                               ('GRID',(0,0),(-1,-1),1,colors.black)]))
    story.append(table)
    story.append(Spacer(1, 12))

    # Results Table
    if results:
        headers = ['Subject', 'CA1', 'CA2', 'Exam', 'Total', 'Grade', 'Term']
        result_data = [headers] + [[r.subject, r.ca1, r.ca2, r.exam, r.total, r.grade, r.term] for r in results]
        result_table = Table(result_data)
        result_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND',(0,1),(-1,-1),colors.beige),
            ('GRID',(0,0),(-1,-1),1,colors.black)
        ]))
        story.append(result_table)
    else:
        story.append(Paragraph("No results available.", styles['Normal']))

    doc.build(story)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f'{student.username}_results.pdf', mimetype='application/pdf')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_users()
    app.run(debug=True)