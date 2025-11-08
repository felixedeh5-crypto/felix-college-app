Skip to content
Navigation Menu
felixedeh5-crypto
felix-college-app

Code
Issues
Pull requests
Actions
Projects
Wiki
Commit d0dfea6
felixedeh5-crypto
felixedeh5-crypto
committed
6 minutes ago
Super Admin + Class-Specific Teachers + Clean Login
main
1 parent 
ad0c36a
 commit 
d0dfea6
1 file changed
+159
-61
lines changed
Search within code
 
‎app.py‎
Original file line number	Diff line number	Diff line change
@@ -2,7 +2,7 @@
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
import bcrypt
from datetime import date
from datetime import date, datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
@@ -11,28 +11,35 @@

app = Flask(__name__)
app.config['SECRET_KEY'] = 'felixcollege2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/database.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# === MODELS ===
# === DATABASE MODELS ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'superadmin', 'teacher', 'student'
    class_name = db.Column(db.String(10))
    is_form_teacher = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    def is_authenticated(self): return True
    def is_active(self): return self.is_active
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)
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
@@ -58,39 +65,71 @@ class Attendance(db.Model):
def load_user(user_id):
    return db.session.get(User, int(user_id))

# === CREATE DATABASE & USERS ON FIRST RUN ===
def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='superadmin').first():
            # Super Admin
            pwd = bcrypt.hashpw('superpass123'.encode(), bcrypt.gensalt()).decode()
            superadmin = User(username='superadmin', password=pwd, role='superadmin')
            db.session.add(superadmin)
            # Form Teachers
            teacher_pwd = bcrypt.hashpw('teacher123'.encode(), bcrypt.gensalt()).decode()
            classes = ['JSS1', 'JSS2', 'JSS3', 'SSS1', 'SSS2', 'SSS3']
            for cls in classes:
                t = User(username=f'formteacher_{cls.lower()}', password=teacher_pwd, role='teacher', class_name=cls, is_form_teacher=True)
                db.session.add(t)
            # 50 Students
            student_pwd = bcrypt.hashpw('123'.encode(), bcrypt.gensalt()).decode()
            for i in range(50):
                class_name = classes[i % len(classes)]
                username = f'student_{i+1}_{class_name.lower()}'
                user = User(username=username, password=student_pwd, role='student', class_name=class_name)
                db.session.add(user)
            db.session.commit()
# === CREATE SUPER ADMIN + CLASS-SPECIFIC FORM TEACHERS + 50 STUDENTS ===
def create_users():
    if not User.query.filter_by(username='superadmin').first():
        # Super Admin (YOU - ONLY ONE)
        super_pwd = bcrypt.hashpw('superpass123'.encode(), bcrypt.gensalt()).decode()
        superadmin = User(username='superadmin', password=super_pwd, role='superadmin')
        db.session.add(superadmin)
        # Class-Specific Form Teachers (One per class)
        teacher_pwd = bcrypt.hashpw('teacher123'.encode(), bcrypt.gensalt()).decode()
        classes = ['JSS1', 'JSS2', 'JSS3', 'SSS1', 'SSS2', 'SSS3']
        for cls in classes:
            t = User(username=f'formteacher_{cls.lower()}', password=teacher_pwd, role='teacher', class_name=cls, is_form_teacher=True)
            db.session.add(t)
        # Default Student
        student_pwd = bcrypt.hashpw('123'.encode(), bcrypt.gensalt()).decode()
        student = User(username='jss1_student', password=student_pwd, role='student', class_name='JSS1')
        db.session.add(student)
        # 50 Students Across Classes
        for i in range(50):
            class_name = classes[i % len(classes)]
            username = f'student_{i+1}_{class_name.lower()}'
            user = User(username=username, password=student_pwd, role='student', class_name=class_name)
            db.session.add(user)
        db.session.commit()

# === ROUTES ===
@app.route('/')
def home():
    init_db()  # THIS FIXES EVERYTHING
    return redirect(url_for('login'))

# === REGISTRATION PAGE (Now only for Super Admin) ===
@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if current_user.role != 'superadmin':
        flash('Only Super Admin can register new users!')
        return redirect(url_for('teacher_dash' if current_user.role == 'teacher' else 'student_dash'))
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
        flash('User registered!')
        return redirect(url_for('admin_dash'))
    return render_template('register.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
@@ -113,116 +152,175 @@ def logout():
    logout_user()
    return redirect(url_for('login'))

# === STUDENT DASHBOARD ===
@app.route('/student')
@login_required
def student_dash():
    if current_user.role != 'student': return redirect(url_for('login'))
    if current_user.role != 'student':
        return redirect(url_for('login'))
    results = Result.query.filter_by(student_id=current_user.id).all()
    return render_template('student_dashboard.html', results=results, name=current_user.username)

# === TEACHER DASHBOARD (Class-Specific) ===
@app.route('/teacher')
@login_required
def teacher_dash():
    if current_user.role != 'teacher': return redirect(url_for('login'))
    if current_user.role != 'teacher':
        return redirect(url_for('login'))
    students = User.query.filter_by(class_name=current_user.class_name, role='student').all()
    return render_template('teacher_dashboard.html', students=students)

# === MARK ATTENDANCE (Form Teacher Only - Class-Specific) ===
@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    if not (current_user.is_form_teacher and current_user.role == 'teacher'):
        flash('Only Form Teachers!')
        flash('Only Form Teachers can mark attendance!')
        return redirect(url_for('teacher_dash'))
    students = User.query.filter_by(class_name=current_user.class_name, role='student').all()
    today = date.today()
    if request.method == 'POST':
        for s in students:
            status = request.form.get(f'status_{s.id}')
        for student in students:
            status = request.form.get(f'status_{student.id}')
            if status:
                rec = Attendance.query.filter_by(student_id=s.id, date=today).first()
                if rec:
                    rec.status = status
                record = Attendance.query.filter_by(student_id=student.id, date=today).first()
                if record:
                    record.status = status
                else:
                    db.session.add(Attendance(student_id=s.id, class_name=s.class_name, date=today, status=status, marked_by=current_user.id))
                    new_att = Attendance(student_id=student.id, class_name=student.class_name, date=today, status=status, marked_by=current_user.id)
                    db.session.add(new_att)
        db.session.commit()
        flash('Attendance saved!')
        flash('Attendance saved for ' + current_user.class_name + '!')
        return redirect(url_for('teacher_dash'))
    records = Attendance.query.filter_by(date=today, class_name=current_user.class_name).all()
    att_dict = {r.student_id: r.status for r in records}
    return render_template('attendance.html', students=students, att_dict=att_dict, today=today)

# === UPLOAD RESULT (Teachers upload for their class only) ===
@app.route('/upload_result', methods=['GET', 'POST'])
@login_required
def upload_result():
    if current_user.role != 'teacher': return redirect(url_for('login'))
    if current_user.role != 'teacher':
        flash('Only teachers can upload results!')
        return redirect(url_for('login'))
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
        total = ca1 + ca2 + exam
        grade = 'A' if total >= 70 else 'B' if total >= 60 else 'C' if total >= 50 else 'D' if total >= 40 else 'F'
        result = Result(student_id=sid, subject=subject, ca1=ca1, ca2=ca2, exam=exam, total=total, grade=grade, term=term, session=session)
        db.session.add(result)
        db.session.commit()
        flash('Result saved!')
        flash('Result saved for ' + current_user.class_name + '!')
        return redirect(url_for('teacher_dash'))
    return render_template('upload_result.html', students=students)

# === SUPER ADMIN PANEL (YOU ONLY - Full Edit Across Board) ===
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dash():
    if current_user.username != 'superadmin':
        flash('Only Super Admin!')
        flash('Only Super Admin can access this panel!')
        return redirect(url_for('teacher_dash' if current_user.role == 'teacher' else 'student_dash'))
    users = User.query.all()
    # Super Admin Add Student
    if request.method == 'POST' and 'add_student' in request.form:
        username = request.form['student_username']
        pwd = bcrypt.hashpw(request.form['student_password'].encode(), bcrypt.gensalt()).decode()
        password = bcrypt.hashpw(request.form['student_password'].encode(), bcrypt.gensalt()).decode()
        class_name = request.form['student_class']
        db.session.add(User(username=username, password=pwd, role='student', class_name=class_name))
        student = User(username=username, password=password, role='student', class_name=class_name)
        db.session.add(student)
        db.session.commit()
        flash('Student added!')
        return redirect(url_for('admin_dash'))
    # Super Admin Add Teacher
    if request.method == 'POST' and 'add_teacher' in request.form:
        username = request.form['teacher_username']
        pwd = bcrypt.hashpw(request.form['teacher_password'].encode(), bcrypt.gensalt()).decode()
        password = bcrypt.hashpw(request.form['teacher_password'].encode(), bcrypt.gensalt()).decode()
        class_name = request.form['teacher_class']
        is_form = 'form_teacher' in request.form
        db.session.add(User(username=username, password=pwd, role='teacher', class_name=class_name, is_form_teacher=is_form))
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
    story.append(Paragraph("FELIX COLLEGE - RESULT SHEET", styles['Title']))
    title = Paragraph("FELIX COLLEGE - RESULT SHEET", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    data = [['Student:', student.username], ['Class:', student.class_name]]
    table = Table(data)
    table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
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
    if results:
        headers = ['Subject', 'CA1', 'CA2', 'Exam', 'Total', 'Grade', 'Term']
        result_data = [headers] + [[r.subject, r.ca1, r.ca2, r.exam, r.total, r.grade, r.term] for r in results]
        result_table = Table(result_data)
        result_table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
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
        story.append(Paragraph("No results.", styles['Normal']))
        story.append(Paragraph("No results available.", styles['Normal']))
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'{student.username}_results.pdf', mimetype='application/pdf')

# === RUN ON RENDER ===
init_db()  # THIS RUNS ON EVERY START
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_users()
    app.run(debug=True)
0 commit comments
Comments
0
 (0)
Comment
You're not receiving notifications from this thread.

