from twilio.rest import Client
import os
from models import db, SMSNotification, User
from datetime import datetime
import africastalking

class SMSService:
    def __init__(self):
        # Twilio configuration
        self.twilio_account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        self.twilio_auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        self.twilio_phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
        
        # Africa's Talking configuration (for African countries)
        self.at_username = os.environ.get('AFRICASTALKING_USERNAME')
        self.at_api_key = os.environ.get('AFRICASTALKING_API_KEY')
        
        self.use_twilio = bool(self.twilio_account_sid)
        self.use_africastalking = bool(self.at_username)
        
        if self.use_twilio:
            self.twilio_client = Client(self.twilio_account_sid, self.twilio_auth_token)
        
        if self.use_africastalking:
            africastalking.initialize(self.at_username, self.at_api_key)
            self.at_sms = africastalking.SMS
    
    def send_sms(self, phone_number, message, user_id=None, notification_type='general'):
        """Send SMS to a phone number"""
        if not phone_number:
            return None, "No phone number provided"
        
        # Format phone number (ensure international format)
        phone_number = self.format_phone_number(phone_number)
        
        # Create SMS record
        sms_record = SMSNotification(
            recipient_phone=phone_number,
            message=message,
            notification_type=notification_type,
            user_id=user_id,
            status='pending'
        )
        db.session.add(sms_record)
        db.session.flush()
        
        # Try to send via Twilio first
        if self.use_twilio:
            try:
                twilio_message = self.twilio_client.messages.create(
                    body=message,
                    from_=self.twilio_phone_number,
                    to=phone_number
                )
                
                sms_record.status = 'sent'
                sms_record.message_id = twilio_message.sid
                sms_record.cost = float(twilio_message.price) if twilio_message.price else 0
                db.session.commit()
                
                return twilio_message.sid, None
                
            except Exception as e:
                sms_record.status = 'failed'
                db.session.commit()
                return None, str(e)
        
        # Try Africa's Talking
        elif self.use_africastalking:
            try:
                response = self.at_sms.send(message, [phone_number])
                
                if response['SMSMessageData']['Recipients'][0]['status'] == 'Success':
                    sms_record.status = 'sent'
                    sms_record.message_id = response['SMSMessageData']['MessageId']
                    db.session.commit()
                    return response['SMSMessageData']['MessageId'], None
                else:
                    sms_record.status = 'failed'
                    db.session.commit()
                    return None, "Failed to send SMS"
                    
            except Exception as e:
                sms_record.status = 'failed'
                db.session.commit()
                return None, str(e)
        
        else:
            sms_record.status = 'failed'
            db.session.commit()
            return None, "No SMS service configured"
    
    def format_phone_number(self, phone):
        """Format phone number to international format"""
        # Remove any non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # South African numbers
        if phone.startswith('0'):
            phone = '+27' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+' + phone
        
        return phone
    
    def send_bulk_sms(self, phone_numbers, message, user_ids=None, notification_type='bulk'):
        """Send SMS to multiple recipients"""
        results = []
        
        for i, phone in enumerate(phone_numbers):
            user_id = user_ids[i] if user_ids and i < len(user_ids) else None
            message_id, error = self.send_sms(phone, message, user_id, notification_type)
            
            results.append({
                'phone': phone,
                'success': message_id is not None,
                'message_id': message_id,
                'error': error
            })
        
        return results
    
    def send_attendance_alert(self, parent_phone, learner_name, date, status):
        """Send attendance alert to parent"""
        message = f"School Alert: {learner_name} was marked {status} on {date}. Please login to the portal for more details."
        return self.send_sms(parent_phone, message, notification_type='attendance')
    
    def send_grade_alert(self, parent_phone, learner_name, subject, grade):
        """Send grade alert to parent"""
        message = f"School Alert: {learner_name} received {grade} in {subject}. Login to view full report card."
        return self.send_sms(parent_phone, message, notification_type='grade')
    
    def send_fee_reminder(self, parent_phone, learner_name, amount, due_date):
        """Send fee payment reminder"""
        message = f"Fee Reminder: Outstanding amount of R{amount:,.2f} for {learner_name} is due on {due_date}. Please make payment to avoid penalties."
        return self.send_sms(parent_phone, message, notification_type='fee')
    
    def send_emergency_alert(self, phone_numbers, message):
        """Send emergency alert to multiple recipients"""
        return self.send_bulk_sms(phone_numbers, message, notification_type='emergency')
    
    def send_event_reminder(self, phone_numbers, event_name, event_date, event_time):
        """Send event reminder"""
        message = f"Reminder: {event_name} is scheduled for {event_date} at {event_time}. We look forward to seeing you!"
        return self.send_bulk_sms(phone_numbers, message, notification_type='event')