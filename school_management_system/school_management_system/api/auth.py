from flask_restful import Resource, reqparse
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from models import db, User, Learner, Teacher, Parent, MobileDevice
from werkzeug.security import check_password_hash
from datetime import timedelta

class MobileAuthResource(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', required=True)
        parser.add_argument('password', required=True)
        parser.add_argument('device_token', required=False)
        parser.add_argument('device_type', required=False)
        parser.add_argument('app_version', required=False)
        args = parser.parse_args()
        
        user = User.query.filter_by(username=args['username']).first()
        
        if not user or not user.check_password(args['password']):
            return {'error': 'Invalid credentials'}, 401
        
        if not user.is_active:
            return {'error': 'Account is inactive'}, 403
        
        # Register device for push notifications
        if args.get('device_token'):
            device = MobileDevice.query.filter_by(
                user_id=user.id,
                device_token=args['device_token']
            ).first()
            
            if not device:
                device = MobileDevice(
                    user_id=user.id,
                    device_token=args['device_token'],
                    device_type=args.get('device_type', 'unknown'),
                    app_version=args.get('app_version', '1.0')
                )
                db.session.add(device)
            else:
                device.last_active = datetime.utcnow()
            db.session.commit()
        
        # Create tokens
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                'username': user.username,
                'role': user.role,
                'full_name': user.full_name
            },
            expires_delta=timedelta(days=7)  # Longer expiry for mobile
        )
        refresh_token = create_refresh_token(identity=user.id)
        
        # Get user profile based on role
        profile = self.get_user_profile(user)
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'profile_picture': user.profile_picture,
                'profile': profile
            }
        }, 200
    
    def get_user_profile(self, user):
        """Get additional profile info based on role"""
        profile = {}
        
        if user.role == 'learner':
            learner = Learner.query.filter_by(user_id=user.id).first()
            if learner:
                profile = {
                    'student_number': learner.student_number,
                    'grade': learner.grade,
                    'class_id': learner.class_id,
                    'class_name': learner.class_.name if learner.class_ else None
                }
        elif user.role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=user.id).first()
            if teacher:
                profile = {
                    'employee_id': teacher.employee_id,
                    'qualification': teacher.qualification,
                    'department': teacher.department
                }
        elif user.role == 'parent':
            parent = Parent.query.filter_by(user_id=user.id).first()
            if parent:
                children = []
                for child in parent.children:
                    children.append({
                        'id': child.id,
                        'name': child.user.full_name,
                        'grade': child.grade,
                        'student_number': child.student_number
                    })
                profile = {'children': children}
        
        return profile

class TokenRefreshResource(Resource):
    @jwt_required(refresh=True)
    def post(self):
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return {'error': 'User not found'}, 404
        
        new_access_token = create_access_token(
            identity=user.id,
            additional_claims={
                'username': user.username,
                'role': user.role,
                'full_name': user.full_name
            },
            expires_delta=timedelta(days=7)
        )
        
        return {'access_token': new_access_token}, 200