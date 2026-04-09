from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Learner, Teacher, Assignment, Submission, Attendance, Fee, Notification
from sqlalchemy import func
from datetime import datetime, timedelta

class MobileDashboardResource(Resource):
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if user.role == 'learner':
            return self.get_learner_dashboard(user)
        elif user.role == 'teacher':
            return self.get_teacher_dashboard(user)
        elif user.role == 'parent':
            return self.get_parent_dashboard(user)
        else:
            return self.get_admin_dashboard(user)
    
    def get_learner_dashboard(self, user):
        learner = Learner.query.filter_by(user_id=user.id).first()
        
        # Upcoming assignments
        upcoming_assignments = Assignment.query.filter_by(
            class_id=learner.class_id,
            is_published=True
        ).filter(
            Assignment.due_date > datetime.utcnow()
        ).order_by(Assignment.due_date).limit(5).all()
        
        # Recent grades
        recent_grades = db.session.query(
            Grade, Subject
        ).join(Subject).filter(
            Grade.learner_id == learner.id
        ).order_by(Grade.date.desc()).limit(5).all()
        
        # Attendance summary
        thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
        attendance_summary = db.session.query(
            func.count(Attendance.id).label('total'),
            func.sum(db.case((Attendance.status == 'present', 1), else_=0)).label('present')
        ).filter(
            Attendance.learner_id == learner.id,
            Attendance.date >= thirty_days_ago
        ).first()
        
        attendance_rate = (attendance_summary.present / attendance_summary.total * 100) if attendance_summary.total else 0
        
        # Today's timetable
        today_entries = TimetableEntry.query.filter_by(
            class_id=learner.class_id,
            day_of_week=datetime.utcnow().weekday()
        ).order_by(TimetableEntry.period).all()
        
        # Unread notifications
        unread_count = Notification.query.filter_by(
            target_user_id=user.id,
            is_read=False
        ).count()
        
        return {
            'learner': {
                'id': learner.id,
                'name': user.full_name,
                'grade': learner.grade,
                'class': learner.class_.name if learner.class_ else None
            },
            'upcoming_assignments': [{
                'id': a.id,
                'title': a.title,
                'subject': a.subject.name,
                'due_date': a.due_date.isoformat(),
                'max_score': a.max_score
            } for a in upcoming_assignments],
            'recent_grades': [{
                'id': g.id,
                'subject': s.name,
                'score': g.score,
                'max_score': g.max_score,
                'percentage': round(g.score / g.max_score * 100, 1),
                'date': g.date.isoformat()
            } for g, s in recent_grades],
            'attendance_rate': round(attendance_rate, 1),
            'today_timetable': [{
                'period': e.period,
                'subject': e.subject.name,
                'teacher': e.teacher.user.full_name,
                'start_time': str(e.start_time),
                'end_time': str(e.end_time),
                'room': e.room
            } for e in today_entries],
            'unread_notifications': unread_count
        }, 200
    
    def get_teacher_dashboard(self, user):
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        
        # Classes today
        today = datetime.utcnow().weekday()
        today_classes = TimetableEntry.query.filter_by(
            teacher_id=teacher.id,
            day_of_week=today
        ).order_by(TimetableEntry.period).all()
        
        # Pending grading
        pending_submissions = Submission.query.join(Assignment).filter(
            Assignment.teacher_id == teacher.id,
            Submission.status == 'submitted',
            Submission.score.is_(None)
        ).count()
        
        # Upcoming virtual classes
        upcoming_virtual = VirtualClass.query.filter_by(
            teacher_id=teacher.id,
            is_active=True
        ).filter(
            VirtualClass.start_time > datetime.utcnow()
        ).order_by(VirtualClass.start_time).limit(3).all()
        
        # Class performance summary
        classes = Class.query.filter_by(teacher_id=teacher.id).all()
        class_performance = []
        for cls in classes:
            avg_grade = db.session.query(
                func.avg(Grade.score / Grade.max_score * 100)
            ).join(Learner).filter(
                Learner.class_id == cls.id,
                Grade.recorded_at >= datetime.utcnow() - timedelta(days=30)
            ).scalar()
            
            class_performance.append({
                'class_id': cls.id,
                'class_name': cls.name,
                'average': round(avg_grade, 1) if avg_grade else None,
                'student_count': cls.learners.count()
            })
        
        return {
            'teacher': {
                'id': teacher.id,
                'name': user.full_name,
                'employee_id': teacher.employee_id
            },
            'today_classes': [{
                'period': c.period,
                'class': c.class_.name,
                'subject': c.subject.name,
                'start_time': str(c.start_time),
                'end_time': str(c.end_time),
                'room': c.room
            } for c in today_classes],
            'pending_grading': pending_submissions,
            'upcoming_virtual_classes': [{
                'id': vc.id,
                'title': vc.title,
                'class': vc.class_.name,
                'start_time': vc.start_time.isoformat(),
                'meeting_url': vc.meeting_url
            } for vc in upcoming_virtual],
            'class_performance': class_performance,
            'total_students': sum(c['student_count'] for c in class_performance)
        }, 200
    
    def get_parent_dashboard(self, user):
        parent = Parent.query.filter_by(user_id=user.id).first()
        children_data = []
        
        for child in parent.children:
            # Recent grades for child
            recent_grades = Grade.query.filter_by(
                learner_id=child.id
            ).order_by(Grade.date.desc()).limit(3).all()
            
            # Attendance
            thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
            attendance = db.session.query(
                func.count(Attendance.id).label('total'),
                func.sum(db.case((Attendance.status == 'present', 1), else_=0)).label('present')
            ).filter(
                Attendance.learner_id == child.id,
                Attendance.date >= thirty_days_ago
            ).first()
            
            attendance_rate = (attendance.present / attendance.total * 100) if attendance.total else 0
            
            # Outstanding fees
            fees = Fee.query.filter_by(learner_id=child.id).all()
            total_fees = sum(f.amount for f in fees)
            paid_fees = sum(f.paid_amount for f in fees)
            
            children_data.append({
                'id': child.id,
                'name': child.user.full_name,
                'grade': child.grade,
                'class': child.class_.name if child.class_ else None,
                'recent_grades': [{
                    'subject': g.subject.name,
                    'score': f"{g.score}/{g.max_score}",
                    'percentage': round(g.score / g.max_score * 100, 1)
                } for g in recent_grades],
                'attendance_rate': round(attendance_rate, 1),
                'fee_status': {
                    'total': total_fees,
                    'paid': paid_fees,
                    'outstanding': total_fees - paid_fees
                }
            })
        
        return {
            'parent': {
                'id': parent.id,
                'name': user.full_name
            },
            'children': children_data
        }, 200
    
    def get_admin_dashboard(self, user):
        # System overview
        total_learners = Learner.query.count()
        total_teachers = Teacher.query.count()
        total_classes = Class.query.count()
        
        # Today's attendance
        today = datetime.utcnow().date()
        attendance = db.session.query(
            func.count(Attendance.id).label('total'),
            func.sum(db.case((Attendance.status == 'present', 1), else_=0)).label('present')
        ).filter(Attendance.date == today).first()
        
        attendance_rate = (attendance.present / attendance.total * 100) if attendance.total else 0
        
        # Fee collection
        fee_stats = db.session.query(
            func.sum(Fee.amount).label('total'),
            func.sum(Fee.paid_amount).label('collected')
        ).first()
        
        # Recent activities
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        
        return {
            'stats': {
                'total_learners': total_learners,
                'total_teachers': total_teachers,
                'total_classes': total_classes,
                'attendance_rate': round(attendance_rate, 1),
                'fee_collection_rate': round((fee_stats.collected / fee_stats.total * 100) if fee_stats.total else 0, 1)
            },
            'recent_users': [{
                'id': u.id,
                'name': u.full_name,
                'role': u.role,
                'created_at': u.created_at.isoformat()
            } for u in recent_users]
        }, 200