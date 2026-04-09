import zoomus
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
from models import db, VirtualClass, VirtualClassAttendee, User, Learner, Teacher
from datetime import datetime, timedelta
import json
import requests

class VideoConferenceService:
    def __init__(self):
        # Zoom configuration
        self.zoom_api_key = os.environ.get('ZOOM_API_KEY')
        self.zoom_api_secret = os.environ.get('ZOOM_API_SECRET')
        self.zoom_user_id = os.environ.get('ZOOM_USER_ID')
        
        # Google Meet configuration
        self.google_credentials_file = os.environ.get('GOOGLE_CREDENTIALS_FILE')
        self.google_token_file = os.environ.get('GOOGLE_TOKEN_FILE', 'token.json')
        
        self.zoom_client = None
        self.google_service = None
        
        self.initialize_services()
    
    def initialize_services(self):
        """Initialize video conferencing services"""
        if self.zoom_api_key and self.zoom_api_secret:
            self.zoom_client = zoomus.ZoomClient(self.zoom_api_key, self.zoom_api_secret)
        
        if self.google_credentials_file and os.path.exists(self.google_credentials_file):
            self.initialize_google_meet()
    
    def initialize_google_meet(self):
        """Initialize Google Meet service"""
        try:
            creds = None
            if os.path.exists(self.google_token_file):
                creds = Credentials.from_authorized_user_file(self.google_token_file, 
                    ['https://www.googleapis.com/auth/calendar'])
            
            if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.google_credentials_file,
                    ['https://www.googleapis.com/auth/calendar']
                )
                creds = flow.run_local_server(port=0)
                
                with open(self.google_token_file, 'w') as token:
                    token.write(creds.to_json())
            
            self.google_service = build('calendar', 'v3', credentials=creds)
            
        except Exception as e:
            print(f"Failed to initialize Google Meet: {e}")
    
    def create_zoom_meeting(self, title, start_time, duration=60, password=None, settings=None):
        """Create a Zoom meeting"""
        if not self.zoom_client:
            return None, "Zoom service not configured"
        
        try:
            meeting_data = {
                'topic': title,
                'type': 2,  # Scheduled meeting
                'start_time': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'duration': duration,
                'timezone': 'Africa/Johannesburg',
                'password': password or self.generate_meeting_password(),
                'settings': {
                    'host_video': True,
                    'participant_video': True,
                    'join_before_host': True,
                    'mute_upon_entry': True,
                    'waiting_room': False,
                    'auto_recording': 'cloud',
                    **(settings or {})
                }
            }
            
            response = self.zoom_client.meeting.create(
                user_id=self.zoom_user_id,
                **meeting_data
            )
            
            meeting_info = response.json()
            
            return {
                'meeting_id': meeting_info['id'],
                'meeting_url': meeting_info['join_url'],
                'password': meeting_info['password'],
                'start_url': meeting_info.get('start_url'),
                'platform': 'zoom'
            }, None
            
        except Exception as e:
            return None, str(e)
    
    def create_google_meet(self, title, start_time, end_time, attendees=None, description=None):
        """Create Google Meet meeting"""
        if not self.google_service:
            return None, "Google Meet service not configured"
        
        try:
            event = {
                'summary': title,
                'description': description or title,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Africa/Johannesburg',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Africa/Johannesburg',
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"school-meet-{datetime.utcnow().timestamp()}",
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'
                        }
                    }
                },
                'attendees': [{'email': email} for email in (attendees or [])]
            }
            
            event = self.google_service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1
            ).execute()
            
            meeting_url = event.get('hangoutLink')
            meeting_id = event['id']
            
            return {
                'meeting_id': meeting_id,
                'meeting_url': meeting_url,
                'platform': 'google_meet',
                'calendar_event_id': event['id']
            }, None
            
        except Exception as e:
            return None, str(e)
    
    def schedule_virtual_class(self, class_id, subject_id, teacher_id, title, start_time, 
                              duration=60, platform='zoom', recurrence=None):
        """Schedule a virtual class"""
        teacher = Teacher.query.get(teacher_id)
        class_obj = Class.query.get(class_id)
        
        if not teacher or not class_obj:
            return None, "Invalid teacher or class"
        
        # Create meeting
        if platform == 'zoom':
            meeting_data, error = self.create_zoom_meeting(title, start_time, duration)
        elif platform == 'google_meet':
            end_time = start_time + timedelta(minutes=duration)
            meeting_data, error = self.create_google_meet(title, start_time, end_time)
        else:
            return None, "Unsupported platform"
        
        if error:
            return None, error
        
        # Save virtual class record
        virtual_class = VirtualClass(
            title=title,
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            meeting_id=meeting_data['meeting_id'],
            meeting_url=meeting_data['meeting_url'],
            meeting_password=meeting_data.get('password'),
            start_time=start_time,
            end_time=start_time + timedelta(minutes=duration),
            duration=duration,
            recurrence=recurrence,
            platform=platform
        )
        
        db.session.add(virtual_class)
        db.session.commit()
        
        # Send notifications to students
        self.notify_students(virtual_class, class_obj, teacher)
        
        return virtual_class, None
    
    def notify_students(self, virtual_class, class_obj, teacher):
        """Notify students about virtual class"""
        from email_service import send_email
        from sms_service import SMSService
        
        sms_service = SMSService()
        
        learners = class_obj.learners.all()
        
        for learner in learners:
            # Send email
            if learner.user.email_notifications:
                send_email(
                    learner.user.email,
                    f"Virtual Class Scheduled: {virtual_class.title}",
                    "virtual_class_notification",
                    learner=learner,
                    virtual_class=virtual_class,
                    teacher=teacher
                )
            
            # Send SMS if parent has phone number
            if learner.parent and learner.parent.user.phone:
                message = f"Virtual Class: {virtual_class.title} with {teacher.user.full_name} on {virtual_class.start_time.strftime('%d %b at %H:%M')}. Join: {virtual_class.meeting_url}"
                sms_service.send_sms(learner.parent.user.phone, message, notification_type='virtual_class')
    
    def get_meeting_recordings(self, meeting_id, platform='zoom'):
        """Get recordings for a meeting"""
        if platform == 'zoom':
            return self.get_zoom_recordings(meeting_id)
        elif platform == 'google_meet':
            return self.get_google_meet_recordings(meeting_id)
        
        return None, "Unsupported platform"
    
    def get_zoom_recordings(self, meeting_id):
        """Get Zoom meeting recordings"""
        if not self.zoom_client:
            return None, "Zoom service not configured"
        
        try:
            response = self.zoom_client.recording.list(meeting_id=meeting_id)
            recordings = response.json()
            
            recording_files = []
            for file in recordings.get('recording_files', []):
                recording_files.append({
                    'id': file['id'],
                    'type': file['recording_type'],
                    'url': file['download_url'],
                    'duration': file.get('duration', 0),
                    'size': file.get('file_size', 0)
                })
            
            return recording_files, None
            
        except Exception as e:
            return None, str(e)
    
    def track_attendance(self, virtual_class_id, learner_id, join_time=None):
        """Track virtual class attendance"""
        attendee = VirtualClassAttendee.query.filter_by(
            virtual_class_id=virtual_class_id,
            learner_id=learner_id
        ).first()
        
        if attendee:
            if not attendee.leave_time and join_time:
                # Still in session
                return attendee
            elif not attendee.leave_time:
                # Mark leave time
                attendee.leave_time = datetime.utcnow()
                attendee.duration_attended = int((attendee.leave_time - attendee.join_time).total_seconds() / 60)
        else:
            attendee = VirtualClassAttendee(
                virtual_class_id=virtual_class_id,
                learner_id=learner_id,
                join_time=join_time or datetime.utcnow()
            )
            db.session.add(attendee)
        
        db.session.commit()
        return attendee
    
    def generate_meeting_password(self, length=6):
        """Generate random meeting password"""
        import random
        import string
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def get_upcoming_classes(self, user_id, role):
        """Get upcoming virtual classes for a user"""
        now = datetime.utcnow()
        
        if role == 'learner':
            learner = Learner.query.filter_by(user_id=user_id).first()
            if learner:
                classes = VirtualClass.query.filter_by(
                    class_id=learner.class_id,
                    is_active=True
                ).filter(
                    VirtualClass.start_time > now
                ).order_by(VirtualClass.start_time).all()
                return classes
        
        elif role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=user_id).first()
            if teacher:
                classes = VirtualClass.query.filter_by(
                    teacher_id=teacher.id,
                    is_active=True
                ).filter(
                    VirtualClass.start_time > now
                ).order_by(VirtualClass.start_time).all()
                return classes
        
        return []