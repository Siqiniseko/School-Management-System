from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date, time
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    profile_picture = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    email_notifications = db.Column(db.Boolean, default=True)
    
    # Relationships
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False)
    learner_profile = db.relationship('Learner', backref='user', uselist=False)
    parent_profile = db.relationship('Parent', backref='user', uselist=False)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Teacher(db.Model):
    __tablename__ = 'teachers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    employee_id = db.Column(db.String(20), unique=True)
    qualification = db.Column(db.String(200))
    subjects_taught = db.Column(db.Text)
    hire_date = db.Column(db.Date)
    department = db.Column(db.String(100))
    office_location = db.Column(db.String(50))
    
    classes = db.relationship('Class', backref='teacher', lazy='dynamic')
    assignments = db.relationship('Assignment', backref='teacher', lazy='dynamic')
    timetable_entries = db.relationship('TimetableEntry', backref='teacher', lazy='dynamic')

class Learner(db.Model):
    __tablename__ = 'learners'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    student_number = db.Column(db.String(20), unique=True)
    grade = db.Column(db.Integer)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'))
    date_of_birth = db.Column(db.Date)
    enrollment_date = db.Column(db.Date)
    medical_conditions = db.Column(db.Text)
    emergency_contact = db.Column(db.String(20))
    
    attendance_records = db.relationship('Attendance', backref='learner', lazy='dynamic')
    fee_records = db.relationship('Fee', backref='learner', lazy='dynamic')
    grades = db.relationship('Grade', backref='learner', lazy='dynamic')
    submissions = db.relationship('Submission', backref='learner', lazy='dynamic')

class Parent(db.Model):
    __tablename__ = 'parents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    occupation = db.Column(db.String(100))
    relationship = db.Column(db.String(50))
    work_phone = db.Column(db.String(20))
    
    children = db.relationship('Learner', backref='parent', lazy='dynamic')
    messages_sent = db.relationship('ParentTeacherMessage', foreign_keys='ParentTeacherMessage.parent_id', backref='parent', lazy='dynamic')

class Class(db.Model):
    __tablename__ = 'classes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(5))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    capacity = db.Column(db.Integer, default=30)
    room_number = db.Column(db.String(10))
    academic_year = db.Column(db.String(10))
    
    learners = db.relationship('Learner', backref='class_', lazy='dynamic')
    subjects = db.relationship('ClassSubject', backref='class_', lazy='dynamic')
    timetable_entries = db.relationship('TimetableEntry', backref='class_', lazy='dynamic')
    assignments = db.relationship('Assignment', backref='class_', lazy='dynamic')

class Subject(db.Model):
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True)
    description = db.Column(db.Text)
    credits = db.Column(db.Integer)
    syllabus = db.Column(db.Text)
    
    classes = db.relationship('ClassSubject', backref='subject', lazy='dynamic')
    teachers = db.relationship('TeacherSubject', backref='subject', lazy='dynamic')
    timetable_entries = db.relationship('TimetableEntry', backref='subject', lazy='dynamic')
    assignments = db.relationship('Assignment', backref='subject', lazy='dynamic')

class ClassSubject(db.Model):
    __tablename__ = 'class_subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))

class TeacherSubject(db.Model):
    __tablename__ = 'teacher_subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))

class TimetableEntry(db.Model):
    __tablename__ = 'timetable_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    day_of_week = db.Column(db.Integer)  # 0=Monday, 6=Sunday
    period = db.Column(db.Integer)  # 1-8
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    room = db.Column(db.String(20))
    academic_year = db.Column(db.String(10))
    term = db.Column(db.String(20))

class Assignment(db.Model):
    __tablename__ = 'assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    max_score = db.Column(db.Float, default=100.0)
    weight = db.Column(db.Float, default=1.0)
    assignment_type = db.Column(db.String(50))  # homework, project, test, exam
    allow_late_submission = db.Column(db.Boolean, default=False)
    late_penalty = db.Column(db.Float, default=0.0)  # percentage deduction
    attachments = db.Column(db.Text)  # JSON array of file paths
    instructions = db.Column(db.Text)
    is_published = db.Column(db.Boolean, default=False)
    
    submissions = db.relationship('Submission', backref='assignment', lazy='dynamic')

class Submission(db.Model):
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'))
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    files = db.Column(db.Text)  # JSON array of file paths
    comments = db.Column(db.Text)
    score = db.Column(db.Float)
    feedback = db.Column(db.Text)
    graded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    graded_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='submitted')  # draft, submitted, graded, returned
    is_late = db.Column(db.Boolean, default=False)
    plagiarism_score = db.Column(db.Float)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20))  # present, absent, late, excused
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    remarks = db.Column(db.Text)
    period = db.Column(db.Integer)  # For period-wise attendance

class Fee(db.Model):
    __tablename__ = 'fees'
    
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'))
    fee_type = db.Column(db.String(50))
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date)
    paid_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')
    payment_date = db.Column(db.Date)
    payment_method = db.Column(db.String(50))
    transaction_id = db.Column(db.String(100))
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    academic_year = db.Column(db.String(10))
    term = db.Column(db.String(20))
    receipt_number = db.Column(db.String(50), unique=True)
    payment_proof = db.Column(db.String(200))  # File path for payment proof

class Grade(db.Model):
    __tablename__ = 'grades'
    
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    assessment_type = db.Column(db.String(50))
    score = db.Column(db.Float)
    max_score = db.Column(db.Float, default=100.0)
    weight = db.Column(db.Float, default=1.0)
    term = db.Column(db.String(20))
    academic_year = db.Column(db.String(10))
    date = db.Column(db.Date)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    remarks = db.Column(db.Text)
    grade_letter = db.Column(db.String(2))

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50))
    target_role = db.Column(db.String(20))
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    email_sent = db.Column(db.Boolean, default=False)

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subject = db.Column(db.String(200))
    content = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    parent_message_id = db.Column(db.Integer, db.ForeignKey('messages.id'))  # For replies
    attachment = db.Column(db.String(200))
    
    replies = db.relationship('Message', backref=db.backref('parent', remote_side=[id]))

class ParentTeacherMessage(db.Model):
    __tablename__ = 'parent_teacher_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'))
    subject = db.Column(db.String(200))
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_by = db.Column(db.String(20))  # 'parent' or 'teacher'
    is_read = db.Column(db.Boolean, default=False)
    meeting_requested = db.Column(db.Boolean, default=False)
    meeting_date = db.Column(db.DateTime)
    meeting_status = db.Column(db.String(20))  # requested, confirmed, cancelled, completed

class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    report_type = db.Column(db.String(50))  # academic, attendance, financial, behavior
    generated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    parameters = db.Column(db.Text)  # JSON of report parameters
    file_path = db.Column(db.String(200))
    format = db.Column(db.String(10))  # PDF, Excel, CSV
    size = db.Column(db.Integer)  # File size in bytes
    download_count = db.Column(db.Integer, default=0)

class AnalyticsCache(db.Model):
    __tablename__ = 'analytics_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(200), unique=True)
    data = db.Column(db.Text)  # JSON data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)

    # Add these to your existing models.py

class MobileDevice(db.Model):
    __tablename__ = 'mobile_devices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    device_token = db.Column(db.String(255))
    device_type = db.Column(db.String(20))  # ios, android
    app_version = db.Column(db.String(20))
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    push_enabled = db.Column(db.Boolean, default=True)

class SMSNotification(db.Model):
    __tablename__ = 'sms_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient_phone = db.Column(db.String(20))
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20))  # pending, sent, delivered, failed
    message_id = db.Column(db.String(100))
    notification_type = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    cost = db.Column(db.Float)

class PaymentTransaction(db.Model):
    __tablename__ = 'payment_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(100), unique=True)
    fee_id = db.Column(db.Integer, db.ForeignKey('fees.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    amount = db.Column(db.Float)
    currency = db.Column(db.String(3), default='ZAR')
    payment_method = db.Column(db.String(50))  # stripe, paypal, card, eft
    status = db.Column(db.String(20))  # pending, completed, failed, refunded
    payment_gateway = db.Column(db.String(50))
    gateway_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    receipt_url = db.Column(db.String(255))
    refund_amount = db.Column(db.Float, default=0.0)
    refund_reason = db.Column(db.Text)

class VirtualClass(db.Model):
    __tablename__ = 'virtual_classes'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    meeting_id = db.Column(db.String(100), unique=True)
    meeting_url = db.Column(db.String(500))
    meeting_password = db.Column(db.String(50))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # in minutes
    recurrence = db.Column(db.String(50))  # once, daily, weekly
    platform = db.Column(db.String(50))  # zoom, google_meet
    recording_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    attendees = db.relationship('VirtualClassAttendee', backref='virtual_class', lazy='dynamic')

class VirtualClassAttendee(db.Model):
    __tablename__ = 'virtual_class_attendees'
    
    id = db.Column(db.Integer, primary_key=True)
    virtual_class_id = db.Column(db.Integer, db.ForeignKey('virtual_classes.id'))
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'))
    join_time = db.Column(db.DateTime)
    leave_time = db.Column(db.DateTime)
    duration_attended = db.Column(db.Integer)  # in minutes
    device_type = db.Column(db.String(50))
    connection_quality = db.Column(db.String(20))

class PlagiarismCheck(db.Model):
    __tablename__ = 'plagiarism_checks'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'))
    similarity_score = db.Column(db.Float)
    matched_sources = db.Column(db.Text)  # JSON array of sources
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
    ai_generated_probability = db.Column(db.Float)
    detailed_report = db.Column(db.Text)
    status = db.Column(db.String(20))  # pending, completed, failed

class PredictiveModel(db.Model):
    __tablename__ = 'predictive_models'
    
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100))
    model_type = db.Column(db.String(50))  # performance, dropout, engagement
    model_data = db.Column(db.LargeBinary)  # Pickled model
    accuracy = db.Column(db.Float)
    last_trained = db.Column(db.DateTime)
    features_used = db.Column(db.Text)  # JSON array
    is_active = db.Column(db.Boolean, default=True)

class StudentPrediction(db.Model):
    __tablename__ = 'student_predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'))
    prediction_type = db.Column(db.String(50))
    predicted_value = db.Column(db.Float)
    confidence = db.Column(db.Float)
    factors = db.Column(db.Text)  # JSON
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    model_version = db.Column(db.String(50))