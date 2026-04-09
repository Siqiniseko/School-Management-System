from flask import Blueprint
from flask_restful import Api
from .auth import MobileAuthResource, TokenRefreshResource
from .dashboard import MobileDashboardResource
from .assignments import MobileAssignmentResource, MobileSubmissionResource
from .attendance import MobileAttendanceResource
from .grades import MobileGradeResource
from .messages import MobileMessageResource
from .timetable import MobileTimetableResource
from .payments import MobilePaymentResource
from .virtual_class import MobileVirtualClassResource

mobile_api = Blueprint('mobile_api', __name__)
api = Api(mobile_api)

# Auth endpoints
api.add_resource(MobileAuthResource, '/auth/login', '/auth/register')
api.add_resource(TokenRefreshResource, '/auth/refresh')

# Dashboard
api.add_resource(MobileDashboardResource, '/dashboard')

# Assignments
api.add_resource(MobileAssignmentResource, '/assignments', '/assignments/<int:assignment_id>')
api.add_resource(MobileSubmissionResource, '/assignments/<int:assignment_id>/submit')

# Attendance
api.add_resource(MobileAttendanceResource, '/attendance', '/attendance/<int:attendance_id>')

# Grades
api.add_resource(MobileGradeResource, '/grades', '/grades/<int:grade_id>')

# Messages
api.add_resource(MobileMessageResource, '/messages', '/messages/<int:message_id>')

# Timetable
api.add_resource(MobileTimetableResource, '/timetable')

# Payments
api.add_resource(MobilePaymentResource, '/payments', '/payments/<string:transaction_id>')

# Virtual Classes
api.add_resource(MobileVirtualClassResource, '/virtual-classes', '/virtual-classes/<int:class_id>')