from models import db, User, Learner, Teacher, Class, Subject, Grade, Attendance, Fee, Assignment, Submission
from sqlalchemy import func, and_, extract
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict
import json

class AnalyticsService:
    def __init__(self):
        self.cache = {}
    
    def get_dashboard_stats(self):
        """Get comprehensive dashboard statistics"""
        stats = {
            'overview': self.get_overview_stats(),
            'enrollment_trends': self.get_enrollment_trends(),
            'performance_metrics': self.get_performance_metrics(),
            'attendance_analytics': self.get_attendance_analytics(),
            'financial_analytics': self.get_financial_analytics(),
            'engagement_metrics': self.get_engagement_metrics()
        }
        return stats
    
    def get_overview_stats(self):
        """Get overview statistics"""
        total_learners = Learner.query.count()
        total_teachers = Teacher.query.count()
        total_classes = Class.query.count()
        total_subjects = Subject.query.count()
        
        # Active users in last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users = User.query.filter(User.last_login >= thirty_days_ago).count()
        
        return {
            'total_learners': total_learners,
            'total_teachers': total_teachers,
            'total_classes': total_classes,
            'total_subjects': total_subjects,
            'active_users': active_users,
            'learner_teacher_ratio': round(total_learners / total_teachers, 1) if total_teachers > 0 else 0
        }
    
    def get_enrollment_trends(self):
        """Analyze enrollment trends by grade and year"""
        enrollment_by_grade = db.session.query(
            Learner.grade,
            func.count(Learner.id).label('count')
        ).group_by(Learner.grade).all()
        
        # Monthly enrollment trends for current year
        current_year = datetime.utcnow().year
        monthly_enrollment = db.session.query(
            extract('month', Learner.enrollment_date).label('month'),
            func.count(Learner.id).label('count')
        ).filter(
            extract('year', Learner.enrollment_date) == current_year
        ).group_by('month').all()
        
        return {
            'by_grade': {grade: count for grade, count in enrollment_by_grade},
            'monthly': {int(month): count for month, count in monthly_enrollment}
        }
    
    def get_performance_metrics(self):
        """Calculate academic performance metrics"""
        # Average grades by subject
        subject_performance = db.session.query(
            Subject.name,
            func.avg(Grade.score / Grade.max_score * 100).label('avg_score'),
            func.count(Grade.id).label('total_assessments')
        ).join(Grade).group_by(Subject.id).all()
        
        # Grade distribution
        grade_distribution = db.session.query(
            func.floor(Grade.score / Grade.max_score * 100 / 10) * 10,
            func.count(Grade.id)
        ).group_by(
            func.floor(Grade.score / Grade.max_score * 100 / 10)
        ).all()
        
        # Top performing students
        top_students = db.session.query(
            Learner,
            func.avg(Grade.score / Grade.max_score * 100).label('avg_score')
        ).join(Grade).group_by(Learner.id).order_by(func.avg(Grade.score).desc()).limit(10).all()
        
        return {
            'subject_performance': [
                {'subject': name, 'avg_score': round(avg, 2), 'count': count}
                for name, avg, count in subject_performance
            ],
            'grade_distribution': {int(score_range): count for score_range, count in grade_distribution},
            'top_students': [
                {'name': student.user.full_name, 'avg_score': round(score, 2)}
                for student, score in top_students
            ]
        }
    
    def get_attendance_analytics(self):
        """Analyze attendance patterns"""
        # Overall attendance rate
        total_records = Attendance.query.count()
        present_records = Attendance.query.filter_by(status='present').count()
        overall_rate = (present_records / total_records * 100) if total_records > 0 else 0
        
        # Attendance by day of week
        attendance_by_day = db.session.query(
            func.strftime('%w', Attendance.date).label('day'),
            func.count(Attendance.id).label('total'),
            func.sum(db.case((Attendance.status == 'present', 1), else_=0)).label('present')
        ).group_by('day').all()
        
        # Chronic absenteeism (less than 80% attendance)
        thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
        chronic_absentees = db.session.query(
            Learner,
            func.count(Attendance.id).label('total_days'),
            func.sum(db.case((Attendance.status == 'present', 1), else_=0)).label('present_days')
        ).join(Attendance).filter(
            Attendance.date >= thirty_days_ago
        ).group_by(Learner.id).having(
            func.sum(db.case((Attendance.status == 'present', 1), else_=0)) / func.count(Attendance.id) < 0.8
        ).all()
        
        return {
            'overall_rate': round(overall_rate, 2),
            'by_day': [
                {'day': day, 'rate': round((present/total*100) if total > 0 else 0, 2)}
                for day, total, present in attendance_by_day
            ],
            'chronic_absentees': [
                {
                    'name': student.user.full_name,
                    'rate': round((present/total*100) if total > 0 else 0, 2)
                }
                for student, total, present in chronic_absentees
            ]
        }
    
    def get_financial_analytics(self):
        """Analyze financial data"""
        # Fee collection rates
        fee_stats = db.session.query(
            func.sum(Fee.amount).label('total'),
            func.sum(Fee.paid_amount).label('collected'),
            func.count(Fee.id).label('count')
        ).first()
        
        # Monthly collection trends
        current_year = datetime.utcnow().year
        monthly_collections = db.session.query(
            extract('month', Fee.payment_date).label('month'),
            func.sum(Fee.paid_amount).label('amount')
        ).filter(
            extract('year', Fee.payment_date) == current_year
        ).group_by('month').all()
        
        # Outstanding fees by grade
        outstanding_by_grade = db.session.query(
            Learner.grade,
            func.sum(Fee.amount - Fee.paid_amount).label('outstanding')
        ).join(Fee).filter(
            Fee.status != 'paid'
        ).group_by(Learner.grade).all()
        
        # Fee type distribution
        fee_type_distribution = db.session.query(
            Fee.fee_type,
            func.sum(Fee.amount).label('total')
        ).group_by(Fee.fee_type).all()
        
        return {
            'collection_rate': round((fee_stats.collected / fee_stats.total * 100) if fee_stats.total else 0, 2),
            'total_expected': float(fee_stats.total or 0),
            'total_collected': float(fee_stats.collected or 0),
            'monthly_trend': {int(month): float(amount) for month, amount in monthly_collections},
            'outstanding_by_grade': {grade: float(amount) for grade, amount in outstanding_by_grade},
            'fee_type_distribution': {type_: float(total) for type_, total in fee_type_distribution}
        }
    
    def get_engagement_metrics(self):
        """Analyze student and teacher engagement"""
        # Assignment submission rates
        assignment_stats = db.session.query(
            func.count(Assignment.id).label('total'),
            func.count(Submission.id).label('submitted')
        ).outerjoin(Submission).first()
        
        # Average time to submit assignments
        avg_submission_time = db.session.query(
            func.avg(
                func.julianday(Submission.submitted_at) - func.julianday(Assignment.created_at)
            )
        ).join(Assignment).filter(Submission.submitted_at.isnot(None)).scalar()
        
        # Teacher activity
        teacher_activity = db.session.query(
            User.full_name,
            func.count(Assignment.id).label('assignments'),
            func.count(Grade.id).label('grades')
        ).join(Teacher).outerjoin(Assignment).outerjoin(Grade).group_by(User.id).all()
        
        # Message activity
        message_stats = db.session.query(
            func.count(Message.id).label('total'),
            func.count(db.case((Message.is_read == True, 1))).label('read')
        ).first()
        
        return {
            'assignment_submission_rate': round((assignment_stats.submitted / assignment_stats.total * 100) if assignment_stats.total else 0, 2),
            'avg_submission_days': round(avg_submission_time, 1) if avg_submission_time else 0,
            'teacher_activity': [
                {'name': name, 'assignments': assignments, 'grades': grades}
                for name, assignments, grades in teacher_activity
            ],
            'message_read_rate': round((message_stats.read / message_stats.total * 100) if message_stats.total else 0, 2)
        }
    
    def generate_heatmap_data(self, data_type='attendance'):
        """Generate data for heatmap visualization"""
        if data_type == 'attendance':
            # Attendance heatmap by day and period
            heatmap_data = db.session.query(
                Attendance.date,
                Attendance.period,
                func.count(Attendance.id),
                func.sum(db.case((Attendance.status == 'present', 1), else_=0))
            ).group_by(Attendance.date, Attendance.period).all()
            
            return [
                {
                    'date': str(date),
                    'period': period,
                    'rate': round((present/total*100) if total > 0 else 0, 2)
                }
                for date, period, total, present in heatmap_data
            ]
        
        elif data_type == 'grades':
            # Grade distribution heatmap
            grade_data = db.session.query(
                Learner.grade,
                Subject.name,
                func.avg(Grade.score / Grade.max_score * 100)
            ).join(Grade).join(Subject).group_by(Learner.grade, Subject.id).all()
            
            return [
                {
                    'grade': grade,
                    'subject': subject,
                    'avg_score': round(score, 2)
                }
                for grade, subject, score in grade_data
            ]
    
    def predict_student_performance(self, learner_id):
        """Predict student performance using simple trend analysis"""
        learner = Learner.query.get(learner_id)
        if not learner:
            return None
        
        # Get historical grades
        grades = Grade.query.filter_by(learner_id=learner_id).order_by(Grade.date).all()
        
        if len(grades) < 3:
            return {'prediction': 'Insufficient data', 'confidence': 0}
        
        # Simple linear regression for each subject
        predictions = {}
        subjects = set(g.subject_id for g in grades)
        
        for subject_id in subjects:
            subject_grades = [g for g in grades if g.subject_id == subject_id]
            if len(subject_grades) >= 3:
                scores = [(i, (g.score / g.max_score) * 100) for i, g in enumerate(subject_grades)]
                
                # Simple trend calculation
                x = [s[0] for s in scores]
                y = [s[1] for s in scores]
                
                if len(x) > 1:
                    slope = (y[-1] - y[0]) / (x[-1] - x[0]) if x[-1] != x[0] else 0
                    next_score = min(100, max(0, y[-1] + slope))
                    
                    subject = Subject.query.get(subject_id)
                    predictions[subject.name] = {
                        'current_avg': sum(y) / len(y),
                        'trend': 'improving' if slope > 0 else 'declining' if slope < 0 else 'stable',
                        'predicted_next': round(next_score, 1),
                        'confidence': min(90, len(subject_grades) * 20)
                    }
        
        return predictions
    
    def get_recommendations(self, user_role, user_id):
        """Generate personalized recommendations"""
        recommendations = []
        
        if user_role == 'learner':
            learner = Learner.query.filter_by(user_id=user_id).first()
            if learner:
                # Check attendance
                attendance_rate = self.get_attendance_analytics()['overall_rate']
                if attendance_rate < 85:
                    recommendations.append({
                        'type': 'attendance',
                        'priority': 'high',
                        'message': 'Your attendance is below 85%. Regular attendance is crucial for academic success.',
                        'action': 'Review attendance record'
                    })
                
                # Check for missing assignments
                missing_submissions = db.session.query(Assignment).filter(
                    Assignment.class_id == learner.class_id,
                    ~Assignment.submissions.any(Submission.learner_id == learner.id),
                    Assignment.due_date < datetime.utcnow()
                ).count()
                
                if missing_submissions > 0:
                    recommendations.append({
                        'type': 'assignments',
                        'priority': 'high',
                        'message': f'You have {missing_submissions} overdue assignments.',
                        'action': 'Submit assignments'
                    })
                
                # Grade-based recommendations
                low_grades = db.session.query(
                    Subject.name,
                    func.avg(Grade.score / Grade.max_score * 100).label('avg')
                ).join(Grade).filter(
                    Grade.learner_id == learner.id
                ).group_by(Subject.id).having(func.avg(Grade.score / Grade.max_score * 100) < 60).all()
                
                for subject, avg in low_grades:
                    recommendations.append({
                        'type': 'academic',
                        'priority': 'medium',
                        'message': f'Your average in {subject} is {round(avg, 1)}%. Consider seeking extra help.',
                        'action': f'Contact {subject} teacher'
                    })
        
        elif user_role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=user_id).first()
            if teacher:
                # Check for ungraded assignments
                ungraded = Submission.query.filter(
                    Submission.assignment.has(Assignment.teacher_id == teacher.id),
                    Submission.status == 'submitted',
                    Submission.score.is_(None)
                ).count()
                
                if ungraded > 0:
                    recommendations.append({
                        'type': 'grading',
                        'priority': 'high',
                        'message': f'You have {ungraded} assignments waiting to be graded.',
                        'action': 'Grade assignments'
                    })
                
                # Check classes with low performance
                low_performing_classes = db.session.query(
                    Class.name,
                    func.avg(Grade.score / Grade.max_score * 100).label('avg')
                ).join(Learner).join(Grade).filter(
                    Class.teacher_id == teacher.id
                ).group_by(Class.id).having(func.avg(Grade.score / Grade.max_score * 100) < 65).all()
                
                for class_name, avg in low_performing_classes:
                    recommendations.append({
                        'type': 'performance',
                        'priority': 'medium',
                        'message': f'Class {class_name} average is {round(avg, 1)}%. May need additional support.',
                        'action': f'Review {class_name} performance'
                    })
        
        elif user_role == 'admin':
            # Admin recommendations
            overdue_fees = Fee.query.filter(
                Fee.due_date < datetime.utcnow().date(),
                Fee.status != 'paid'
            ).count()
            
            if overdue_fees > 0:
                recommendations.append({
                    'type': 'financial',
                    'priority': 'high',
                    'message': f'There are {overdue_fees} overdue fee payments.',
                    'action': 'Review outstanding fees'
                })
            
            # Check attendance issues
            attendance_analytics = self.get_attendance_analytics()
            if attendance_analytics['overall_rate'] < 90:
                recommendations.append({
                    'type': 'attendance',
                    'priority': 'medium',
                    'message': f'Overall attendance rate is {attendance_analytics["overall_rate"]}%.',
                    'action': 'Review attendance policies'
                })
        
        return recommendations