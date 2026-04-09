from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import os
from datetime import datetime
from models import db, Learner, Grade, Attendance, Fee, Class, Subject

class ReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER
        )
    
    def generate_academic_report(self, learner_id, term, academic_year):
        """Generate comprehensive academic report for a learner"""
        learner = Learner.query.get(learner_id)
        if not learner:
            return None
        
        filename = f"academic_report_{learner.student_number}_{term}_{academic_year}.pdf"
        filepath = os.path.join('reports', filename)
        os.makedirs('reports', exist_ok=True)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        story = []
        
        # Title
        story.append(Paragraph(f"Academic Progress Report", self.title_style))
        story.append(Paragraph(f"{learner.user.full_name} - Grade {learner.grade}", self.styles['Heading2']))
        story.append(Paragraph(f"Term {term} - {academic_year}", self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Student Information
        student_info = [
            ["Student Name:", learner.user.full_name],
            ["Student Number:", learner.student_number],
            ["Class:", learner.class_.name if learner.class_ else "N/A"],
            ["Date of Birth:", learner.date_of_birth.strftime('%Y-%m-%d') if learner.date_of_birth else "N/A"]
        ]
        
        info_table = Table(student_info, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 30))
        
        # Grades by Subject
        grades = Grade.query.filter_by(
            learner_id=learner.id,
            term=term,
            academic_year=academic_year
        ).all()
        
        if grades:
            story.append(Paragraph("Subject Grades", self.styles['Heading3']))
            
            grade_data = [["Subject", "Score", "Grade", "Remarks"]]
            for grade in grades:
                subject = Subject.query.get(grade.subject_id)
                grade_data.append([
                    subject.name,
                    f"{grade.score:.1f}/{grade.max_score}",
                    self.calculate_grade_letter(grade.score, grade.max_score),
                    grade.remarks or "-"
                ])
            
            # Calculate average
            avg_score = sum(g.score for g in grades) / len(grades)
            grade_data.append(["", "", "", ""])
            grade_data.append(["Average", f"{avg_score:.1f}%", self.calculate_grade_letter(avg_score, 100), ""])
            
            grade_table = Table(grade_data, colWidths=[2.5*inch, 1.5*inch, 1*inch, 2*inch])
            grade_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -3), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
            ]))
            story.append(grade_table)
            
            # Add grade chart
            chart = self.create_grade_chart(grades)
            story.append(Spacer(1, 20))
            story.append(chart)
        
        # Attendance Summary
        attendance_records = Attendance.query.filter_by(
            learner_id=learner.id
        ).filter(
            Attendance.date.between(f"{academic_year}-01-01", f"{academic_year}-12-31")
        ).all()
        
        if attendance_records:
            story.append(Spacer(1, 20))
            story.append(Paragraph("Attendance Summary", self.styles['Heading3']))
            
            present = sum(1 for r in attendance_records if r.status == 'present')
            absent = sum(1 for r in attendance_records if r.status == 'absent')
            late = sum(1 for r in attendance_records if r.status == 'late')
            total = len(attendance_records)
            
            attendance_data = [
                ["Status", "Days", "Percentage"],
                ["Present", present, f"{(present/total*100):.1f}%" if total > 0 else "0%"],
                ["Absent", absent, f"{(absent/total*100):.1f}%" if total > 0 else "0%"],
                ["Late", late, f"{(late/total*100):.1f}%" if total > 0 else "0%"],
                ["Total", total, "100%"]
            ]
            
            attendance_table = Table(attendance_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
            attendance_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(attendance_table)
        
        # Teacher Comments
        story.append(Spacer(1, 30))
        story.append(Paragraph("Teacher's Comments:", self.styles['Heading4']))
        story.append(Paragraph("Overall performance is satisfactory. Keep up the good work!", self.styles['Normal']))
        
        # Build PDF
        doc.build(story)
        return filepath
    
    def generate_class_report(self, class_id, term, academic_year):
        """Generate class performance report"""
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return None
        
        filename = f"class_report_{class_obj.name}_{term}_{academic_year}.pdf"
        filepath = os.path.join('reports', filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        story = []
        
        story.append(Paragraph(f"Class Performance Report", self.title_style))
        story.append(Paragraph(f"{class_obj.name} - Term {term} {academic_year}", self.styles['Heading2']))
        story.append(Spacer(1, 20))
        
        # Class Statistics
        learners = class_obj.learners.all()
        total_students = len(learners)
        
        # Calculate class averages per subject
        subjects = Subject.query.join(ClassSubject).filter(ClassSubject.class_id == class_id).all()
        
        subject_data = [["Subject", "Class Average", "Highest", "Lowest"]]
        for subject in subjects:
            grades = Grade.query.filter(
                Grade.subject_id == subject.id,
                Grade.term == term,
                Grade.academic_year == academic_year,
                Grade.learner_id.in_([l.id for l in learners])
            ).all()
            
            if grades:
                scores = [g.score for g in grades]
                subject_data.append([
                    subject.name,
                    f"{sum(scores)/len(scores):.1f}%",
                    f"{max(scores):.1f}%",
                    f"{min(scores):.1f}%"
                ])
        
        if len(subject_data) > 1:
            subject_table = Table(subject_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
            subject_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(subject_table)
        
        doc.build(story)
        return filepath
    
    def generate_financial_report(self, start_date, end_date):
        """Generate financial report"""
        filename = f"financial_report_{start_date}_{end_date}.pdf"
        filepath = os.path.join('reports', filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        story = []
        
        story.append(Paragraph("Financial Report", self.title_style))
        story.append(Paragraph(f"Period: {start_date} to {end_date}", self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Fee collection summary
        fees = Fee.query.filter(
            Fee.payment_date.between(start_date, end_date)
        ).all()
        
        total_collected = sum(f.paid_amount for f in fees)
        total_by_type = {}
        for fee in fees:
            total_by_type[fee.fee_type] = total_by_type.get(fee.fee_type, 0) + fee.paid_amount
        
        # Summary table
        summary_data = [["Category", "Amount (R)"]]
        summary_data.append(["Total Collected", f"{total_collected:,.2f}"])
        for fee_type, amount in total_by_type.items():
            summary_data.append([fee_type, f"{amount:,.2f}"])
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),
        ]))
        story.append(summary_table)
        
        doc.build(story)
        return filepath
    
    def generate_attendance_report(self, class_id, month, year):
        """Generate monthly attendance report"""
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return None
        
        filename = f"attendance_report_{class_obj.name}_{month}_{year}.pdf"
        filepath = os.path.join('reports', filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        story = []
        
        story.append(Paragraph(f"Monthly Attendance Report", self.title_style))
        story.append(Paragraph(f"{class_obj.name} - {month}/{year}", self.styles['Heading2']))
        story.append(Spacer(1, 20))
        
        # Get attendance data
        from datetime import datetime
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        learners = class_obj.learners.all()
        
        attendance_data = [["Student Name", "Present", "Absent", "Late", "Attendance %"]]
        for learner in learners:
            records = Attendance.query.filter(
                Attendance.learner_id == learner.id,
                Attendance.date >= start_date,
                Attendance.date < end_date
            ).all()
            
            if records:
                present = sum(1 for r in records if r.status == 'present')
                absent = sum(1 for r in records if r.status == 'absent')
                late = sum(1 for r in records if r.status == 'late')
                total = len(records)
                percentage = (present / total * 100) if total > 0 else 0
                
                attendance_data.append([
                    learner.user.full_name,
                    present,
                    absent,
                    late,
                    f"{percentage:.1f}%"
                ])
        
        attendance_table = Table(attendance_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
        attendance_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(attendance_table)
        
        doc.build(story)
        return filepath
    
    def calculate_grade_letter(self, score, max_score):
        """Calculate letter grade from score"""
        percentage = (score / max_score * 100) if max_score > 0 else 0
        
        if percentage >= 80:
            return 'A'
        elif percentage >= 70:
            return 'B'
        elif percentage >= 60:
            return 'C'
        elif percentage >= 50:
            return 'D'
        elif percentage >= 40:
            return 'E'
        else:
            return 'F'
    
    def create_grade_chart(self, grades):
        """Create a bar chart for grades"""
        drawing = Drawing(400, 200)
        chart = VerticalBarChart()
        chart.x = 50
        chart.y = 50
        chart.width = 300
        chart.height = 125
        
        subjects = []
        scores = []
        for grade in grades:
            subject = Subject.query.get(grade.subject_id)
            subjects.append(subject.name[:10])
            scores.append((grade.score / grade.max_score) * 100)
        
        chart.data = [scores]
        chart.categoryAxis.categoryNames = subjects
        chart.categoryAxis.labels.boxAnchor = 'ne'
        chart.categoryAxis.labels.angle = 45
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = 100
        chart.valueAxis.valueStep = 20
        
        chart.bars[0].fillColor = colors.blue
        
        drawing.add(chart)
        return drawing