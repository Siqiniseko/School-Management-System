from flask_mail import Mail, Message
from flask import current_app, render_template
from threading import Thread
import os

mail = Mail()

def init_mail(app):
    """Initialize mail with app configuration"""
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@school.com')
    mail.init_app(app)

def send_async_email(app, msg):
    """Send email asynchronously"""
    with app.app_context():
        mail.send(msg)

def send_email(to, subject, template, **kwargs):
    """Send email using template"""
    app = current_app._get_current_object()
    
    if not app.config.get('MAIL_USERNAME'):
        # If email not configured, just log
        print(f"Email would be sent to {to}: {subject}")
        return
    
    msg = Message(
        subject=f"[School Management] {subject}",
        recipients=[to] if isinstance(to, str) else to
    )
    
    # Render HTML template
    msg.html = render_template(f'email/{template}.html', **kwargs)
    
    # Send email asynchronously
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()

def send_welcome_email(user):
    """Send welcome email to new user"""
    send_email(
        user.email,
        "Welcome to School Management System",
        "welcome",
        user=user
    )

def send_notification_email(user, notification):
    """Send email notification"""
    if user.email_notifications:
        send_email(
            user.email,
            notification.title,
            "notification",
            user=user,
            notification=notification
        )

def send_assignment_notification(learners, assignment):
    """Send assignment notification to learners"""
    for learner in learners:
        if learner.user.email_notifications:
            send_email(
                learner.user.email,
                f"New Assignment: {assignment.title}",
                "new_assignment",
                learner=learner,
                assignment=assignment
            )

def send_grade_notification(learner, grade):
    """Send grade notification to learner and parent"""
    if learner.user.email_notifications:
        send_email(
            learner.user.email,
            f"New Grade Posted: {grade.subject.name}",
            "new_grade",
            learner=learner,
            grade=grade
        )
    
    if learner.parent and learner.parent.user.email_notifications:
        send_email(
            learner.parent.user.email,
            f"New Grade Posted for {learner.user.full_name}",
            "parent_grade_notification",
            parent=learner.parent,
            learner=learner,
            grade=grade
        )

def send_attendance_alert(learner, attendance_summary):
    """Send attendance alert to parent"""
    if learner.parent and learner.parent.user.email_notifications:
        send_email(
            learner.parent.user.email,
            f"Attendance Alert for {learner.user.full_name}",
            "attendance_alert",
            parent=learner.parent,
            learner=learner,
            summary=attendance_summary
        )

def send_message_notification(receiver, sender, message):
    """Send message notification"""
    if receiver.email_notifications:
        send_email(
            receiver.email,
            f"New Message from {sender.full_name}",
            "new_message",
            receiver=receiver,
            sender=sender,
            message=message
        )