from models import db, User, Teacher, Learner, Parent, Class, Subject, Fee, Notification
from config import Config
from datetime import date, datetime, timedelta

def init_db(app):
    """Initialize the database with tables and default data"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if we need to seed the database
        if User.query.count() == 0:
            seed_database()

def seed_database():
    """Add initial data to the database"""
    
    # Create Admin User
    admin = User(
        username='admin',
        email='admin@school.com',
        role='admin',
        full_name='System Administrator',
        phone='0123456789',
        is_active=True
    )
    admin.set_password('admin123')
    db.session.add(admin)
    
    # Create Teachers
    teacher1_user = User(
        username='zanele.dlamini',
        email='zanele.dlamini@school.com',
        role='teacher',
        full_name='Ms. Zanele Dlamini',
        phone='0821234567'
    )
    teacher1_user.set_password('teacher123')
    db.session.add(teacher1_user)
    db.session.flush()
    
    teacher1 = Teacher(
        user_id=teacher1_user.id,
        employee_id='TCH001',
        qualification='B.Ed Mathematics',
        subjects_taught='["Mathematics", "Physical Sciences"]',
        hire_date=date(2020, 1, 15)
    )
    db.session.add(teacher1)
    
    teacher2_user = User(
        username='john.smith',
        email='john.smith@school.com',
        role='teacher',
        full_name='Mr. John Smith',
        phone='0837654321'
    )
    teacher2_user.set_password('teacher456')
    db.session.add(teacher2_user)
    db.session.flush()
    
    teacher2 = Teacher(
        user_id=teacher2_user.id,
        employee_id='TCH002',
        qualification='BA English Literature',
        subjects_taught='["English", "History"]',
        hire_date=date(2019, 6, 1)
    )
    db.session.add(teacher2)
    
    # Create Subjects
    subjects_data = [
        {'name': 'Mathematics', 'code': 'MATH101', 'credits': 4},
        {'name': 'Physical Sciences', 'code': 'PHY102', 'credits': 4},
        {'name': 'English', 'code': 'ENG101', 'credits': 3},
        {'name': 'Life Sciences', 'code': 'BIO101', 'credits': 3},
        {'name': 'Geography', 'code': 'GEO101', 'credits': 3},
        {'name': 'History', 'code': 'HIS101', 'credits': 3},
        {'name': 'Accounting', 'code': 'ACC101', 'credits': 3},
        {'name': 'Business Studies', 'code': 'BUS101', 'credits': 3}
    ]
    
    for subj in subjects_data:
        subject = Subject(**subj)
        db.session.add(subject)
    
    # Create Classes
    classes_data = [
        {'name': 'Gr 9C', 'grade': 9, 'section': 'C', 'teacher_id': teacher2.id, 'room_number': '101', 'academic_year': '2025'},
        {'name': 'Gr 10A', 'grade': 10, 'section': 'A', 'teacher_id': teacher1.id, 'room_number': '201', 'academic_year': '2025'},
        {'name': 'Gr 11B', 'grade': 11, 'section': 'B', 'teacher_id': teacher2.id, 'room_number': '301', 'academic_year': '2025'},
        {'name': 'Gr 12A', 'grade': 12, 'section': 'A', 'teacher_id': teacher1.id, 'room_number': '401', 'academic_year': '2025'}
    ]
    
    for cls in classes_data:
        class_obj = Class(**cls)
        db.session.add(class_obj)
    
    db.session.flush()
    
    # Create Learners
    learners_data = [
        {
            'user': {'username': 'thabo.ndlovu', 'email': 'thabo@student.school.com', 'full_name': 'Thabo Ndlovu', 'phone': '0781234567'},
            'learner': {'student_number': 'STU001', 'grade': 10, 'date_of_birth': date(2009, 5, 15), 'enrollment_date': date(2025, 1, 10)}
        },
        {
            'user': {'username': 'sarah.jones', 'email': 'sarah@student.school.com', 'full_name': 'Sarah Jones', 'phone': '0798765432'},
            'learner': {'student_number': 'STU002', 'grade': 9, 'date_of_birth': date(2010, 8, 22), 'enrollment_date': date(2025, 1, 10)}
        }
    ]
    
    class_10a = Class.query.filter_by(name='Gr 10A').first()
    class_9c = Class.query.filter_by(name='Gr 9C').first()
    
    for data in learners_data:
        user = User(
            username=data['user']['username'],
            email=data['user']['email'],
            role='learner',
            full_name=data['user']['full_name'],
            phone=data['user']['phone']
        )
        user.set_password('learner123')
        db.session.add(user)
        db.session.flush()
        
        learner_data = data['learner'].copy()
        learner_data['user_id'] = user.id
        if learner_data['grade'] == 10:
            learner_data['class_id'] = class_10a.id
        else:
            learner_data['class_id'] = class_9c.id
        
        learner = Learner(**learner_data)
        db.session.add(learner)
    
    # Create Parent
    parent_user = User(
        username='parent.ndlovu',
        email='parent.ndlovu@email.com',
        role='parent',
        full_name='Mr. Ndlovu',
        phone='0829998888'
    )
    parent_user.set_password('parent123')
    db.session.add(parent_user)
    db.session.flush()
    
    parent = Parent(
        user_id=parent_user.id,
        occupation='Engineer',
        relationship='Father'
    )
    db.session.add(parent)
    db.session.flush()
    
    # Link parent to learner
    thabo = Learner.query.filter_by(student_number='STU001').first()
    thabo.parent_id = parent.id
    
    # Create Accountant
    accountant_user = User(
        username='finance.officer',
        email='finance@school.com',
        role='accountant',
        full_name='Ms. Finance Officer',
        phone='0112345678'
    )
    accountant_user.set_password('account123')
    db.session.add(accountant_user)
    
    # Create Sample Fees
    fees_data = [
        {'learner_id': thabo.id, 'fee_type': 'Tuition', 'amount': 5000, 'due_date': date(2025, 3, 1), 
         'paid_amount': 2000, 'status': 'partial', 'academic_year': '2025', 'term': 'Term 1'},
        {'learner_id': thabo.id, 'fee_type': 'Library', 'amount': 500, 'due_date': date(2025, 2, 15),
         'paid_amount': 500, 'status': 'paid', 'payment_date': date(2025, 2, 10), 'academic_year': '2025', 'term': 'Term 1'}
    ]
    
    for fee in fees_data:
        fee_obj = Fee(**fee)
        db.session.add(fee_obj)
    
    # Create Notifications
    notifications_data = [
        {
            'title': 'School Sports Day',
            'message': 'Annual Sports Day is scheduled for 17 May 2025. All learners should arrive in sports attire. Parents are welcome to attend.',
            'type': 'event',
            'target_role': 'all',
            'created_by': admin.id,
            'expiry_date': date(2025, 5, 18)
        },
        {
            'title': 'Parent-Teacher Meeting',
            'message': 'Parent-Teacher meetings will be held on 25 April 2025 from 14:00 to 17:00.',
            'type': 'important',
            'target_role': 'parent',
            'created_by': admin.id,
            'expiry_date': date(2025, 4, 26)
        },
        {
            'title': 'Term 1 Examinations',
            'message': 'Term 1 examinations will commence on 20 March 2025. Please check the timetable for your schedule.',
            'type': 'important',
            'target_role': 'learner',
            'created_by': admin.id,
            'expiry_date': date(2025, 3, 30)
        }
    ]
    
    for notif in notifications_data:
        notification = Notification(**notif)
        db.session.add(notification)
    
    db.session.commit()
    print("Database seeded successfully!")