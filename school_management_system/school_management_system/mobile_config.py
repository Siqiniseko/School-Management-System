"""
Mobile App API Configuration
This file contains settings for the mobile app integration
"""

MOBILE_API_VERSION = 'v1'
MOBILE_APP_SETTINGS = {
    'min_app_version': '1.0.0',
    'latest_app_version': '1.0.0',
    'features': {
        'push_notifications': True,
        'offline_mode': True,
        'biometric_auth': True,
        'dark_mode': True,
        'file_upload': True,
        'video_streaming': True
    },
    'api_endpoints': {
        'auth': '/api/mobile/auth',
        'dashboard': '/api/mobile/dashboard',
        'assignments': '/api/mobile/assignments',
        'attendance': '/api/mobile/attendance',
        'grades': '/api/mobile/grades',
        'timetable': '/api/mobile/timetable',
        'messages': '/api/mobile/messages',
        'payments': '/api/mobile/payments',
        'virtual_classes': '/api/mobile/virtual-classes'
    }
}

# Push notification settings
PUSH_NOTIFICATION_CONFIG = {
    'firebase': {
        'server_key': 'YOUR_FIREBASE_SERVER_KEY',
        'sender_id': 'YOUR_SENDER_ID'
    },
    'apns': {
        'certificate_path': 'path/to/certificate.pem',
        'key_path': 'path/to/key.pem',
        'bundle_id': 'com.school.management'
    }
}

# Offline sync settings
OFFLINE_SYNC_CONFIG = {
    'sync_interval': 300,  # seconds
    'max_offline_storage': 100 * 1024 * 1024,  # 100MB
    'sync_entities': [
        'assignments',
        'attendance',
        'grades',
        'timetable',
        'messages'
    ]
}