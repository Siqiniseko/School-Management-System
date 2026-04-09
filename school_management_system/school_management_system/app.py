from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Teacher, Learner, Parent, Class, Subject, Attendance, Fee, Notification, Grade
from config import Config
from database import init_db
from datetime import datetime, date, timedelta
from functools import wraps
from sqlalchemy import func
from email_service import init_mail, send_email, send_notification_email, send_assignment_notification
from report_service import ReportGenerator
from analytics_service import AnalyticsService
from file_handler import FileHandler
import json
from datetime import datetime, timedelta
import os
from sms_service import SMSService
from payment_service import PaymentService
from video_conferencing import VideoConferenceService
from plagiarism_detector import PlagiarismDetector
from predictive_analytics import PredictiveAnalytics
from api import mobile_api

# Initialize services
report_generator = ReportGenerator()
analytics_service = AnalyticsService()
file_handler = FileHandler()
sms_service = SMSService()
payment_service = PaymentService()
video_service = VideoConferenceService()
plagiarism_detector = PlagiarismDetector()
predictive_analytics = PredictiveAnalytics()

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Role-based access control decorator
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if current_user.role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Initialize database with tables and sample data
with app.app_context():
    init_db(app)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')  # For demo quick access
        
        # Quick demo access
        if role:
            demo_credentials = {
                'admin': {'username': 'admin', 'password': 'admin123'},
                'teacher': {'username': 'zanele.dlamini', 'password': 'teacher123'},
                'learner': {'username': 'thabo.ndlovu', 'password': 'learner123'},
                'parent': {'username': 'parent.ndlovu', 'password': 'parent123'},
                'accountant': {'username': 'finance.officer', 'password': 'account123'}
            }
            if role in demo_credentials:
                username = demo_credentials[role]['username']
                password = demo_credentials[role]['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=True)
            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Route to appropriate dashboard based on user role"""
    role_dashboard_map = {
        'admin': 'admin_dashboard',
        'teacher': 'teacher_dashboard',
        'learner': 'learner_dashboard',
        'parent': 'parent_dashboard',
        'accountant': 'accountant_dashboard'
    }
    
    dashboard_func = role_dashboard_map.get(current_user.role)
    if dashboard_func:
        return redirect(url_for(dashboard_func))
    else:
        flash('Invalid user role', 'danger')
        return redirect(url_for('logout'))

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    # Statistics for admin dashboard
    total_learners = Learner.query.count()
    total_teachers = Teacher.query.count()
    total_classes = Class.query.count()
    total_subjects = Subject.query.count()
    
    # Grade distribution
    grade_distribution = db.session.query(
        Learner.grade, func.count(Learner.id)
    ).group_by(Learner.grade).all()
    
    grade_stats = {grade: count for grade, count in grade_distribution}
    
    # Today's attendance
    today = date.today()
    today_attendance = db.session.query(
        func.count(Attendance.id),
        func.sum(db.case((Attendance.status == 'present', 1), else_=0))
    ).filter(Attendance.date == today).first()
    
    attendance_percentage = 0
    if today_attendance and today_attendance[0] > 0:
        attendance_percentage = round((today_attendance[1] / today_attendance[0]) * 100)
    
    # Fee collection stats
    fee_stats = db.session.query(
        func.sum(Fee.amount).label('total'),
        func.sum(Fee.paid_amount).label('collected')
    ).first()
    
    total_fees = fee_stats.total or 0
    collected_fees = fee_stats.collected or 0
    outstanding_fees = total_fees - collected_fees
    
    # Recent notifications
    recent_notifications = Notification.query.filter_by(
        is_active=True
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('admin_dashboard.html',
                         total_learners=total_learners,
                         total_teachers=total_teachers,
                         total_classes=total_classes,
                         total_subjects=total_subjects,
                         grade_stats=grade_stats,
                         attendance_percentage=attendance_percentage,
                         collected_fees=collected_fees,
                         outstanding_fees=outstanding_fees,
                         recent_notifications=recent_notifications)

@app.route('/teacher/dashboard')
@login_required
@role_required('teacher')
def teacher_dashboard():
    # Get teacher profile
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    
    # Get teacher's classes
    teacher_classes = Class.query.filter_by(teacher_id=teacher.id).all()
    total_classes = len(teacher_classes)
    
    # Get total learners in teacher's classes
    total_learners = sum(cls.learners.count() for cls in teacher_classes)
    
    # Recent notifications for teachers
    notifications = Notification.query.filter(
        (Notification.target_role == 'all') | (Notification.target_role == 'teacher'),
        Notification.is_active == True
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('teacher_dashboard.html',
                         teacher=teacher,
                         teacher_classes=teacher_classes,
                         total_classes=total_classes,
                         total_learners=total_learners,
                         notifications=notifications)

@app.route('/learner/dashboard')
@login_required
@role_required('learner')
def learner_dashboard():
    # Get learner profile
    learner = Learner.query.filter_by(user_id=current_user.id).first()
    
    # Get learner's class
    learner_class = Class.query.get(learner.class_id) if learner.class_id else None
    
    # Get recent grades
    recent_grades = Grade.query.filter_by(learner_id=learner.id).order_by(Grade.date.desc()).limit(5).all()
    
    # Get attendance summary
    attendance_summary = db.session.query(
        func.count(Attendance.id),
        func.sum(db.case((Attendance.status == 'present', 1), else_=0)),
        func.sum(db.case((Attendance.status == 'absent', 1), else_=0)),
        func.sum(db.case((Attendance.status == 'late', 1), else_=0))
    ).filter(Attendance.learner_id == learner.id).first()
    
    attendance_stats = {
        'total': attendance_summary[0] or 0,
        'present': attendance_summary[1] or 0,
        'absent': attendance_summary[2] or 0,
        'late': attendance_summary[3] or 0
    }
    
    # Get fee status
    fees = Fee.query.filter_by(learner_id=learner.id).all()
    total_fees = sum(fee.amount for fee in fees)
    paid_fees = sum(fee.paid_amount for fee in fees)
    outstanding_fees = total_fees - paid_fees
    
    # Get notifications for learners
    notifications = Notification.query.filter(
        (Notification.target_role == 'all') | (Notification.target_role == 'learner'),
        Notification.is_active == True
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('learner_dashboard.html',
                         learner=learner,
                         learner_class=learner_class,
                         recent_grades=recent_grades,
                         attendance_stats=attendance_stats,
                         total_fees=total_fees,
                         paid_fees=paid_fees,
                         outstanding_fees=outstanding_fees,
                         notifications=notifications)

@app.route('/parent/dashboard')
@login_required
@role_required('parent')
def parent_dashboard():
    # Get parent profile
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    
    # Get children
    children = parent.children.all()
    
    children_data = []
    for child in children:
        child_class = Class.query.get(child.class_id) if child.class_id else None
        
        # Get recent grades for child
        recent_grades = Grade.query.filter_by(learner_id=child.id).order_by(Grade.date.desc()).limit(3).all()
        
        # Get fee status for child
        fees = Fee.query.filter_by(learner_id=child.id).all()
        total_fees = sum(fee.amount for fee in fees)
        paid_fees = sum(fee.paid_amount for fee in fees)
        outstanding_fees = total_fees - paid_fees
        
        children_data.append({
            'learner': child,
            'class': child_class,
            'recent_grades': recent_grades,
            'total_fees': total_fees,
            'paid_fees': paid_fees,
            'outstanding_fees': outstanding_fees
        })
    
    # Get notifications for parents
    notifications = Notification.query.filter(
        (Notification.target_role == 'all') | (Notification.target_role == 'parent'),
        Notification.is_active == True
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('parent_dashboard.html',
                         parent=parent,
                         children_data=children_data,
                         notifications=notifications)

@app.route('/accountant/dashboard')
@login_required
@role_required('accountant')
def accountant_dashboard():
    # Fee collection summary
    fee_summary = db.session.query(
        func.sum(Fee.amount).label('total'),
        func.sum(Fee.paid_amount).label('collected'),
        func.count(Fee.id).label('total_transactions')
    ).first()
    
    total_fees = fee_summary.total or 0
    collected_fees = fee_summary.collected or 0
    outstanding_fees = total_fees - collected_fees
    
    # Recent transactions
    recent_transactions = Fee.query.filter(
        Fee.paid_amount > 0
    ).order_by(Fee.payment_date.desc()).limit(10).all()
    
    # Fee collection by grade
    grade_collection = db.session.query(
        Learner.grade,
        func.sum(Fee.amount).label('total'),
        func.sum(Fee.paid_amount).label('collected')
    ).join(Fee).group_by(Learner.grade).all()
    
    # Pending fees (overdue)
    today = date.today()
    overdue_fees = Fee.query.filter(
        Fee.due_date < today,
        Fee.status.in_(['pending', 'partial'])
    ).all()
    
    return render_template('accountant_dashboard.html',
                         total_fees=total_fees,
                         collected_fees=collected_fees,
                         outstanding_fees=outstanding_fees,
                         recent_transactions=recent_transactions,
                         grade_collection=grade_collection,
                         overdue_fees=overdue_fees)

# API Endpoints for dynamic data
@app.route('/api/attendance/today', methods=['GET'])
@login_required
def api_today_attendance():
    """Get today's attendance statistics"""
    today = date.today()
    attendance = db.session.query(
        func.count(Attendance.id),
        func.sum(db.case((Attendance.status == 'present', 1), else_=0)),
        func.sum(db.case((Attendance.status == 'absent', 1), else_=0)),
        func.sum(db.case((Attendance.status == 'late', 1), else_=0))
    ).filter(Attendance.date == today).first()
    
    return jsonify({
        'total': attendance[0] or 0,
        'present': attendance[1] or 0,
        'absent': attendance[2] or 0,
        'late': attendance[3] or 0,
        'percentage': round((attendance[1] / attendance[0] * 100) if attendance[0] else 0)
    })

@app.route('/api/fees/summary', methods=['GET'])
@login_required
def api_fees_summary():
    """Get fee collection summary"""
    summary = db.session.query(
        func.sum(Fee.amount).label('total'),
        func.sum(Fee.paid_amount).label('collected'),
        func.count(db.case((Fee.status == 'overdue', 1))).label('overdue_count')
    ).first()
    
    return jsonify({
        'total': summary.total or 0,
        'collected': summary.collected or 0,
        'outstanding': (summary.total or 0) - (summary.collected or 0),
        'overdue_count': summary.overdue_count or 0
    })

@app.route('/api/notifications/recent', methods=['GET'])
@login_required
def api_recent_notifications():
    """Get recent notifications for current user"""
    notifications = Notification.query.filter(
        ((Notification.target_role == 'all') | (Notification.target_role == current_user.role) | 
         (Notification.target_user_id == current_user.id)),
        Notification.is_active == True
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.type,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notifications])

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

    # Add these imports at the top
from email_service import init_mail, send_email, send_notification_email, send_assignment_notification
from report_service import ReportGenerator
from analytics_service import AnalyticsService
from file_handler import FileHandler
import json
from datetime import datetime, timedelta
import os

# Initialize services
report_generator = ReportGenerator()
analytics_service = AnalyticsService()
file_handler = FileHandler()

# Add these routes to your existing app.py

# Timetable Management Routes
@app.route('/timetable')
@login_required
def view_timetable():
    """View timetable based on user role"""
    if current_user.role == 'learner':
        learner = Learner.query.filter_by(user_id=current_user.id).first()
        class_id = learner.class_id if learner else None
    elif current_user.role == 'teacher':
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        entries = TimetableEntry.query.filter_by(teacher_id=teacher.id).all() if teacher else []
        return render_template('timetable_teacher.html', entries=entries)
    elif current_user.role == 'admin':
        classes = Class.query.all()
        return render_template('timetable_admin.html', classes=classes)
    else:
        class_id = request.args.get('class_id')
    
    if class_id:
        entries = TimetableEntry.query.filter_by(class_id=class_id).order_by(
            TimetableEntry.day_of_week, TimetableEntry.period
        ).all()
        return render_template('timetable_view.html', entries=entries)
    
    return render_template('timetable.html')

@app.route('/api/timetable', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
@role_required('admin', 'teacher')
def manage_timetable():
    """API endpoint for timetable management"""
    if request.method == 'GET':
        class_id = request.args.get('class_id')
        teacher_id = request.args.get('teacher_id')
        
        query = TimetableEntry.query
        if class_id:
            query = query.filter_by(class_id=class_id)
        if teacher_id:
            query = query.filter_by(teacher_id=teacher_id)
        
        entries = query.order_by(TimetableEntry.day_of_week, TimetableEntry.period).all()
        return jsonify([{
            'id': e.id,
            'class_id': e.class_id,
            'subject_id': e.subject_id,
            'teacher_id': e.teacher_id,
            'day_of_week': e.day_of_week,
            'period': e.period,
            'start_time': str(e.start_time),
            'end_time': str(e.end_time),
            'room': e.room
        } for e in entries])
    
    elif request.method == 'POST':
        data = request.json
        entry = TimetableEntry(
            class_id=data['class_id'],
            subject_id=data['subject_id'],
            teacher_id=data['teacher_id'],
            day_of_week=data['day_of_week'],
            period=data['period'],
            start_time=datetime.strptime(data['start_time'], '%H:%M').time(),
            end_time=datetime.strptime(data['end_time'], '%H:%M').time(),
            room=data.get('room', ''),
            academic_year=datetime.now().year,
            term=data.get('term', 'Term 1')
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify({'success': True, 'id': entry.id})
    
    elif request.method == 'PUT':
        data = request.json
        entry = TimetableEntry.query.get(data['id'])
        if entry:
            for key, value in data.items():
                if key in ['start_time', 'end_time']:
                    value = datetime.strptime(value, '%H:%M').time()
                setattr(entry, key, value)
            db.session.commit()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        entry_id = request.args.get('id')
        entry = TimetableEntry.query.get(entry_id)
        if entry:
            db.session.delete(entry)
            db.session.commit()
        return jsonify({'success': True})

# Assignment Management Routes
@app.route('/assignments')
@login_required
def view_assignments():
    """View assignments based on user role"""
    if current_user.role == 'teacher':
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        assignments = Assignment.query.filter_by(teacher_id=teacher.id).order_by(
            Assignment.due_date.desc()
        ).all() if teacher else []
        return render_template('assignments_teacher.html', assignments=assignments)
    
    elif current_user.role == 'learner':
        learner = Learner.query.filter_by(user_id=current_user.id).first()
        if learner and learner.class_id:
            assignments = Assignment.query.filter_by(
                class_id=learner.class_id,
                is_published=True
            ).order_by(Assignment.due_date.desc()).all()
            return render_template('assignments_learner.html', 
                                 assignments=assignments, 
                                 learner=learner)
    
    return render_template('assignments.html')

@app.route('/assignments/create', methods=['POST'])
@login_required
@role_required('teacher')
def create_assignment():
    """Create new assignment"""
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    
    data = request.form
    files = request.files.getlist('attachments')
    
    assignment = Assignment(
        title=data['title'],
        description=data['description'],
        class_id=data['class_id'],
        subject_id=data['subject_id'],
        teacher_id=teacher.id,
        due_date=datetime.strptime(data['due_date'], '%Y-%m-%dT%H:%M'),
        max_score=float(data.get('max_score', 100)),
        weight=float(data.get('weight', 1.0)),
        assignment_type=data.get('assignment_type', 'homework'),
        allow_late_submission=data.get('allow_late') == 'on',
        late_penalty=float(data.get('late_penalty', 0)),
        instructions=data.get('instructions', ''),
        is_published=data.get('publish') == 'on'
    )
    
    db.session.add(assignment)
    db.session.flush()
    
    # Handle file attachments
    attachments = []
    for file in files:
        if file and file.filename:
            file_info, error = file_handler.save_assignment_file(file, assignment.id)
            if file_info:
                attachments.append(file_info['filename'])
    
    assignment.attachments = json.dumps(attachments)
    db.session.commit()
    
    # Send notifications to learners
    if assignment.is_published:
        learners = Learner.query.filter_by(class_id=assignment.class_id).all()
        send_assignment_notification(learners, assignment)
    
    flash('Assignment created successfully!', 'success')
    return redirect(url_for('view_assignments'))

@app.route('/assignments/<int:assignment_id>/submit', methods=['POST'])
@login_required
@role_required('learner')
def submit_assignment(assignment_id):
    """Submit assignment"""
    learner = Learner.query.filter_by(user_id=current_user.id).first()
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Check if already submitted
    existing = Submission.query.filter_by(
        assignment_id=assignment_id,
        learner_id=learner.id
    ).first()
    
    if existing:
        flash('You have already submitted this assignment.', 'warning')
        return redirect(url_for('view_assignments'))
    
    files = request.files.getlist('files')
    comments = request.form.get('comments', '')
    
    submission = Submission(
        assignment_id=assignment_id,
        learner_id=learner.id,
        comments=comments,
        is_late=datetime.utcnow() > assignment.due_date
    )
    
    db.session.add(submission)
    db.session.flush()
    
    # Handle file uploads
    uploaded_files = []
    for file in files:
        if file and file.filename:
            file_info, error = file_handler.save_submission_file(file, submission.id)
            if file_info:
                uploaded_files.append(file_info['filename'])
    
    submission.files = json.dumps(uploaded_files)
    db.session.commit()
    
    # Notify teacher
    teacher_user = User.query.get(assignment.teacher.user_id)
    notification = Notification(
        title=f"New Submission: {assignment.title}",
        message=f"{learner.user.full_name} has submitted {assignment.title}.",
        type='assignment',
        target_user_id=teacher_user.id,
        created_by=current_user.id
    )
    db.session.add(notification)
    db.session.commit()
    
    send_notification_email(teacher_user, notification)
    
    flash('Assignment submitted successfully!', 'success')
    return redirect(url_for('view_assignments'))

@app.route('/assignments/<int:assignment_id>/grade', methods=['POST'])
@login_required
@role_required('teacher')
def grade_submission(assignment_id):
    """Grade student submission"""
    data = request.json
    submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        learner_id=data['learner_id']
    ).first_or_404()
    
    submission.score = float(data['score'])
    submission.feedback = data.get('feedback', '')
    submission.graded_by = current_user.id
    submission.graded_at = datetime.utcnow()
    submission.status = 'graded'
    
    # Create grade record
    grade = Grade(
        learner_id=data['learner_id'],
        subject_id=submission.assignment.subject_id,
        assessment_type=submission.assignment.assignment_type,
        score=submission.score,
        max_score=submission.assignment.max_score,
        weight=submission.assignment.weight,
        date=datetime.utcnow().date(),
        recorded_by=current_user.id,
        remarks=submission.feedback
    )
    
    db.session.add(grade)
    db.session.commit()
    
    # Notify learner
    learner = Learner.query.get(data['learner_id'])
    send_grade_notification(learner, grade)
    
    return jsonify({'success': True})

# Parent-Teacher Communication Routes
@app.route('/messages')
@login_required
def view_messages():
    """View messages inbox"""
    received = Message.query.filter_by(receiver_id=current_user.id).order_by(
        Message.sent_at.desc()
    ).all()
    
    sent = Message.query.filter_by(sender_id=current_user.id).order_by(
        Message.sent_at.desc()
    ).all()
    
    return render_template('messages.html', received=received, sent=sent)

@app.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    """Send message to another user"""
    data = request.form
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=data['receiver_id'],
        subject=data['subject'],
        content=data['content']
    )
    
    # Handle attachment
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename:
            file_info, error = file_handler.save_file(file, 'messages')
            if file_info:
                message.attachment = file_info['filename']
    
    db.session.add(message)
    db.session.commit()
    
    # Send email notification
    receiver = User.query.get(data['receiver_id'])
    send_message_notification(receiver, current_user, message)
    
    flash('Message sent successfully!', 'success')
    return redirect(url_for('view_messages'))

@app.route('/parent-teacher/meeting', methods=['POST'])
@login_required
@role_required('parent', 'teacher')
def request_meeting():
    """Request parent-teacher meeting"""
    data = request.form
    
    if current_user.role == 'parent':
        parent = Parent.query.filter_by(user_id=current_user.id).first()
        message = ParentTeacherMessage(
            parent_id=parent.id,
            teacher_id=data['teacher_id'],
            learner_id=data['learner_id'],
            subject="Meeting Request",
            message=data['message'],
            sent_by='parent',
            meeting_requested=True,
            meeting_date=datetime.strptime(data['meeting_date'], '%Y-%m-%dT%H:%M') if data.get('meeting_date') else None,
            meeting_status='requested'
        )
    else:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        message = ParentTeacherMessage(
            parent_id=data['parent_id'],
            teacher_id=teacher.id,
            learner_id=data['learner_id'],
            subject="Meeting Request",
            message=data['message'],
            sent_by='teacher',
            meeting_requested=True,
            meeting_date=datetime.strptime(data['meeting_date'], '%Y-%m-%dT%H:%M') if data.get('meeting_date') else None,
            meeting_status='requested'
        )
    
    db.session.add(message)
    db.session.commit()
    
    # Send notifications
    receiver_id = message.teacher.user_id if current_user.role == 'parent' else message.parent.user_id
    receiver = User.query.get(receiver_id)
    
    notification = Notification(
        title="New Meeting Request",
        message=f"{current_user.full_name} has requested a parent-teacher meeting.",
        type='meeting',
        target_user_id=receiver_id,
        created_by=current_user.id
    )
    db.session.add(notification)
    db.session.commit()
    
    send_notification_email(receiver, notification)
    
    flash('Meeting request sent successfully!', 'success')
    return redirect(url_for('view_messages'))

# Report Generation Routes
@app.route('/reports')
@login_required
def reports_dashboard():
    """Reports dashboard"""
    recent_reports = Report.query.order_by(Report.generated_at.desc()).limit(10).all()
    return render_template('reports.html', recent_reports=recent_reports)

@app.route('/reports/generate/academic/<int:learner_id>')
@login_required
@role_required('admin', 'teacher', 'parent')
def generate_academic_report(learner_id):
    """Generate academic report for learner"""
    term = request.args.get('term', 'Term 1')
    year = request.args.get('year', str(datetime.now().year))
    
    filepath = report_generator.generate_academic_report(learner_id, term, year)
    
    if filepath:
        # Save report record
        report = Report(
            title=f"Academic Report - Learner {learner_id}",
            report_type='academic',
            generated_by=current_user.id,
            parameters=json.dumps({'learner_id': learner_id, 'term': term, 'year': year}),
            file_path=filepath,
            format='PDF',
            size=os.path.getsize(filepath)
        )
        db.session.add(report)
        db.session.commit()
        
        return send_file(filepath, as_attachment=True)
    
    flash('Error generating report', 'danger')
    return redirect(url_for('reports_dashboard'))

@app.route('/reports/generate/class/<int:class_id>')
@login_required
@role_required('admin', 'teacher')
def generate_class_report(class_id):
    """Generate class performance report"""
    term = request.args.get('term', 'Term 1')
    year = request.args.get('year', str(datetime.now().year))
    
    filepath = report_generator.generate_class_report(class_id, term, year)
    
    if filepath:
        report = Report(
            title=f"Class Report - Class {class_id}",
            report_type='class_performance',
            generated_by=current_user.id,
            parameters=json.dumps({'class_id': class_id, 'term': term, 'year': year}),
            file_path=filepath,
            format='PDF',
            size=os.path.getsize(filepath)
        )
        db.session.add(report)
        db.session.commit()
        
        return send_file(filepath, as_attachment=True)
    
    flash('Error generating report', 'danger')
    return redirect(url_for('reports_dashboard'))

@app.route('/reports/generate/financial')
@login_required
@role_required('admin', 'accountant')
def generate_financial_report():
    """Generate financial report"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    filepath = report_generator.generate_financial_report(start_date, end_date)
    
    if filepath:
        report = Report(
            title=f"Financial Report {start_date} to {end_date}",
            report_type='financial',
            generated_by=current_user.id,
            parameters=json.dumps({'start_date': start_date, 'end_date': end_date}),
            file_path=filepath,
            format='PDF',
            size=os.path.getsize(filepath)
        )
        db.session.add(report)
        db.session.commit()
        
        return send_file(filepath, as_attachment=True)
    
    flash('Error generating report', 'danger')
    return redirect(url_for('reports_dashboard'))

@app.route('/reports/generate/attendance/<int:class_id>')
@login_required
@role_required('admin', 'teacher')
def generate_attendance_report(class_id):
    """Generate monthly attendance report"""
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    
    filepath = report_generator.generate_attendance_report(class_id, month, year)
    
    if filepath:
        report = Report(
            title=f"Attendance Report - Class {class_id} {month}/{year}",
            report_type='attendance',
            generated_by=current_user.id,
            parameters=json.dumps({'class_id': class_id, 'month': month, 'year': year}),
            file_path=filepath,
            format='PDF',
            size=os.path.getsize(filepath)
        )
        db.session.add(report)
        db.session.commit()
        
        return send_file(filepath, as_attachment=True)
    
    flash('Error generating report', 'danger')
    return redirect(url_for('reports_dashboard'))

# Analytics Routes
@app.route('/analytics')
@login_required
@role_required('admin', 'teacher')
def analytics_dashboard():
    """Advanced analytics dashboard"""
    stats = analytics_service.get_dashboard_stats()
    return render_template('analytics.html', stats=stats)

@app.route('/api/analytics/overview')
@login_required
@role_required('admin', 'teacher')
def api_analytics_overview():
    """Get overview analytics"""
    return jsonify(analytics_service.get_overview_stats())

@app.route('/api/analytics/performance')
@login_required
@role_required('admin', 'teacher')
def api_analytics_performance():
    """Get performance analytics"""
    return jsonify(analytics_service.get_performance_metrics())

@app.route('/api/analytics/attendance')
@login_required
@role_required('admin', 'teacher')
def api_analytics_attendance():
    """Get attendance analytics"""
    return jsonify(analytics_service.get_attendance_analytics())

@app.route('/api/analytics/financial')
@login_required
@role_required('admin', 'accountant')
def api_analytics_financial():
    """Get financial analytics"""
    return jsonify(analytics_service.get_financial_analytics())

@app.route('/api/analytics/engagement')
@login_required
@role_required('admin', 'teacher')
def api_analytics_engagement():
    """Get engagement metrics"""
    return jsonify(analytics_service.get_engagement_metrics())

@app.route('/api/analytics/heatmap/<data_type>')
@login_required
def api_analytics_heatmap(data_type):
    """Get heatmap data for visualization"""
    return jsonify(analytics_service.generate_heatmap_data(data_type))

@app.route('/api/analytics/predict/<int:learner_id>')
@login_required
@role_required('admin', 'teacher', 'parent')
def api_predict_performance(learner_id):
    """Get performance predictions for learner"""
    predictions = analytics_service.predict_student_performance(learner_id)
    return jsonify(predictions or {})

@app.route('/api/analytics/recommendations')
@login_required
def api_recommendations():
    """Get personalized recommendations"""
    recommendations = analytics_service.get_recommendations(
        current_user.role,
        current_user.id
    )
    return jsonify(recommendations)

# File Management Routes
@app.route('/uploads/<path:filename>')
@login_required
def serve_file(filename):
    """Serve uploaded files"""
    return send_from_directory(file_handler.upload_folder, filename)

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """Generic file upload endpoint"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    subfolder = request.form.get('subfolder', '')
    
    file_info, error = file_handler.save_file(file, subfolder)
    
    if error:
        return jsonify({'error': error}), 400
    
    return jsonify(file_info)

@app.route('/api/upload/profile', methods=['POST'])
@login_required
def upload_profile_picture():
    """Upload profile picture"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    file_info, error = file_handler.save_profile_picture(file, current_user.id)
    
    if error:
        return jsonify({'error': error}), 400
    
    # Update user profile
    current_user.profile_picture = file_info['filename']
    db.session.commit()
    
    return jsonify({'success': True, 'filename': file_info['filename']})

# Register mobile API blueprint
app.register_blueprint(mobile_api, url_prefix='/api/mobile')

# SMS Routes
@app.route('/api/sms/send', methods=['POST'])
@login_required
@role_required('admin', 'teacher')
def send_sms():
    """Send SMS notification"""
    data = request.json
    phone = data.get('phone')
    message = data.get('message')
    notification_type = data.get('type', 'general')
    
    message_id, error = sms_service.send_sms(
        phone, message, current_user.id, notification_type
    )
    
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    return jsonify({'success': True, 'message_id': message_id})

@app.route('/api/sms/bulk', methods=['POST'])
@login_required
@role_required('admin')
def send_bulk_sms():
    """Send bulk SMS"""
    data = request.json
    phones = data.get('phones', [])
    message = data.get('message')
    
    results = sms_service.send_bulk_sms(phones, message)
    return jsonify({'success': True, 'results': results})

# Payment Routes
@app.route('/payment/create', methods=['POST'])
@login_required
def create_payment():
    """Create a payment"""
    data = request.json
    fee_id = data.get('fee_id')
    amount = data.get('amount')
    payment_method = data.get('payment_method', 'stripe')
    
    result, error = payment_service.process_fee_payment(
        fee_id, current_user.id, amount, payment_method
    )
    
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    return jsonify({'success': True, 'payment': result})

@app.route('/payment/confirm/<payment_intent_id>', methods=['POST'])
@login_required
def confirm_payment(payment_intent_id):
    """Confirm Stripe payment"""
    success, result = payment_service.confirm_stripe_payment(payment_intent_id)
    
    if success:
        return jsonify({'success': True, 'payment': result})
    
    return jsonify({'success': False, 'error': str(result)}), 400

@app.route('/payment/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook"""
    payload = request.data
    signature = request.headers.get('Stripe-Signature')
    
    success, event_type = payment_service.handle_stripe_webhook(payload, signature)
    
    if success:
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error'}), 400

@app.route('/payment/history')
@login_required
def payment_history():
    """Get payment history"""
    history = payment_service.get_payment_history(current_user.id)
    return jsonify({'success': True, 'history': history})

# Video Conferencing Routes
@app.route('/virtual-class/create', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def create_virtual_class():
    """Create a virtual class"""
    data = request.form
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    
    if not teacher and current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Teacher profile not found'}), 400
    
    teacher_id = teacher.id if teacher else data.get('teacher_id')
    
    start_time = datetime.strptime(data['start_time'], '%Y-%m-%dT%H:%M')
    duration = int(data.get('duration', 60))
    platform = data.get('platform', 'zoom')
    
    virtual_class, error = video_service.schedule_virtual_class(
        class_id=data['class_id'],
        subject_id=data.get('subject_id'),
        teacher_id=teacher_id,
        title=data['title'],
        start_time=start_time,
        duration=duration,
        platform=platform
    )
    
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    return jsonify({
        'success': True,
        'virtual_class': {
            'id': virtual_class.id,
            'meeting_url': virtual_class.meeting_url,
            'meeting_id': virtual_class.meeting_id,
            'password': virtual_class.meeting_password
        }
    })

@app.route('/virtual-class/join/<int:class_id>', methods=['POST'])
@login_required
def join_virtual_class(class_id):
    """Join a virtual class"""
    virtual_class = VirtualClass.query.get_or_404(class_id)
    
    # Track attendance
    if current_user.role == 'learner':
        learner = Learner.query.filter_by(user_id=current_user.id).first()
        if learner:
            video_service.track_attendance(virtual_class.id, learner.id)
    
    return jsonify({
        'success': True,
        'meeting_url': virtual_class.meeting_url,
        'password': virtual_class.meeting_password
    })

@app.route('/virtual-class/upcoming')
@login_required
def upcoming_virtual_classes():
    """Get upcoming virtual classes"""
    classes = video_service.get_upcoming_classes(current_user.id, current_user.role)
    
    return jsonify({
        'success': True,
        'classes': [{
            'id': c.id,
            'title': c.title,
            'start_time': c.start_time.isoformat(),
            'duration': c.duration,
            'meeting_url': c.meeting_url,
            'platform': c.platform
        } for c in classes]
    })

# Plagiarism Detection Routes
@app.route('/api/plagiarism/check/<int:submission_id>', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def check_plagiarism(submission_id):
    """Check submission for plagiarism"""
    check, error = plagiarism_detector.analyze_submission(submission_id)
    
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    return jsonify({
        'success': True,
        'check': {
            'id': check.id,
            'similarity_score': check.similarity_score,
            'ai_probability': check.ai_generated_probability,
            'status': check.status
        }
    })

@app.route('/api/plagiarism/report/<int:submission_id>')
@login_required
@role_required('teacher', 'admin')
def get_plagiarism_report(submission_id):
    """Get detailed plagiarism report"""
    report = plagiarism_detector.get_plagiarism_report(submission_id)
    
    if not report:
        return jsonify({'success': False, 'error': 'Report not found'}), 404
    
    return jsonify({'success': True, 'report': report})

# Predictive Analytics Routes
@app.route('/api/analytics/predict/performance/<int:learner_id>')
@login_required
@role_required('admin', 'teacher', 'parent')
def predict_learner_performance(learner_id):
    """Predict learner performance"""
    prediction, error = predictive_analytics.predict_performance(learner_id)
    
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    return jsonify({'success': True, 'prediction': prediction})

@app.route('/api/analytics/predict/dropout/<int:learner_id>')
@login_required
@role_required('admin', 'teacher')
def predict_dropout_risk(learner_id):
    """Predict dropout risk"""
    prediction, error = predictive_analytics.predict_dropout_risk(learner_id)
    
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    return jsonify({'success': True, 'prediction': prediction})

@app.route('/api/analytics/predict/class/<int:class_id>')
@login_required
@role_required('admin', 'teacher')
def predict_class_performance(class_id):
    """Generate predictions for entire class"""
    predictions = predictive_analytics.generate_class_predictions(class_id)
    
    if not predictions:
        return jsonify({'success': False, 'error': 'Class not found'}), 404
    
    return jsonify({'success': True, 'predictions': predictions})

@app.route('/api/analytics/train', methods=['POST'])
@login_required
@role_required('admin')
def train_models():
    """Train predictive models"""
    data = request.json
    model_type = data.get('model_type', 'all')
    
    results = {}
    
    if model_type in ['all', 'performance']:
        success, message = predictive_analytics.train_performance_model()
        results['performance'] = {'success': success, 'message': message}
    
    if model_type in ['all', 'dropout']:
        success, message = predictive_analytics.train_dropout_model()
        results['dropout'] = {'success': success, 'message': message}
    
    return jsonify({'success': True, 'results': results})

@app.route('/api/analytics/insights')
@login_required
@role_required('admin')
def get_ai_insights():
    """Get AI-powered insights"""
    insights = predictive_analytics.get_analytics_insights()
    return jsonify({'success': True, 'insights': insights})

# Add these routes to app.py

@app.route('/')
def index():
    """Homepage"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/payments')
@login_required
def payments():
    """Payment portal"""
    if current_user.role == 'learner':
        learner = Learner.query.filter_by(user_id=current_user.id).first()
        fees = Fee.query.filter_by(learner_id=learner.id).all() if learner else []
    elif current_user.role == 'parent':
        parent = Parent.query.filter_by(user_id=current_user.id).first()
        fees = []
        if parent:
            for child in parent.children:
                child_fees = Fee.query.filter_by(learner_id=child.id).all()
                fees.extend(child_fees)
    else:
        fees = []
    
    return render_template('payments.html', fees=fees)

@app.route('/virtual-class')
@login_required
def virtual_class():
    """Virtual classroom portal"""
    upcoming = video_service.get_upcoming_classes(current_user.id, current_user.role)
    return render_template('virtual_class.html', upcoming_classes=upcoming)

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('profile.html')

@app.route('/grades')
@login_required
def view_grades():
    """View all grades"""
    if current_user.role == 'learner':
        learner = Learner.query.filter_by(user_id=current_user.id).first()
        grades = Grade.query.filter_by(learner_id=learner.id).order_by(Grade.date.desc()).all() if learner else []
    elif current_user.role == 'parent':
        parent = Parent.query.filter_by(user_id=current_user.id).first()
        grades = []
        if parent:
            for child in parent.children:
                child_grades = Grade.query.filter_by(learner_id=child.id).order_by(Grade.date.desc()).all()
                grades.extend(child_grades)
    else:
        grades = []
    
    return render_template('grades.html', grades=grades)