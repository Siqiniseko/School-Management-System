import stripe
import paypalrestsdk
import os
from models import db, PaymentTransaction, Fee, User
from datetime import datetime
import json

class PaymentService:
    def __init__(self):
        # Stripe configuration
        self.stripe_api_key = os.environ.get('STRIPE_SECRET_KEY')
        self.stripe_webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        # PayPal configuration
        self.paypal_client_id = os.environ.get('PAYPAL_CLIENT_ID')
        self.paypal_client_secret = os.environ.get('PAYPAL_CLIENT_SECRET')
        self.paypal_mode = os.environ.get('PAYPAL_MODE', 'sandbox')
        
        if self.stripe_api_key:
            stripe.api_key = self.stripe_api_key
        
        if self.paypal_client_id:
            paypalrestsdk.configure({
                'mode': self.paypal_mode,
                'client_id': self.paypal_client_id,
                'client_secret': self.paypal_client_secret
            })
    
    def create_stripe_payment_intent(self, amount, currency='zar', metadata=None):
        """Create a Stripe payment intent"""
        try:
            # Convert amount to cents/smallest currency unit
            amount_cents = int(amount * 100)
            
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                automatic_payment_methods={'enabled': True}
            )
            
            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': amount,
                'currency': currency
            }, None
            
        except stripe.error.StripeError as e:
            return None, str(e)
    
    def confirm_stripe_payment(self, payment_intent_id):
        """Confirm Stripe payment"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status == 'succeeded':
                # Record transaction
                transaction = PaymentTransaction.query.filter_by(
                    transaction_id=payment_intent_id
                ).first()
                
                if transaction:
                    transaction.status = 'completed'
                    transaction.completed_at = datetime.utcnow()
                    transaction.gateway_response = json.dumps(intent)
                    db.session.commit()
                
                return True, intent
            else:
                return False, intent
                
        except stripe.error.StripeError as e:
            return False, str(e)
    
    def create_paypal_payment(self, amount, currency='ZAR', description='School Fees', return_url=None, cancel_url=None):
        """Create PayPal payment"""
        payment = paypalrestsdk.Payment({
            'intent': 'sale',
            'payer': {
                'payment_method': 'paypal'
            },
            'redirect_urls': {
                'return_url': return_url or 'http://localhost:5000/payment/success',
                'cancel_url': cancel_url or 'http://localhost:5000/payment/cancel'
            },
            'transactions': [{
                'amount': {
                    'total': str(amount),
                    'currency': currency
                },
                'description': description
            }]
        })
        
        if payment.create():
            # Extract approval URL
            approval_url = None
            for link in payment.links:
                if link.rel == 'approval_url':
                    approval_url = link.href
                    break
            
            return {
                'payment_id': payment.id,
                'approval_url': approval_url,
                'amount': amount,
                'currency': currency
            }, None
        else:
            return None, payment.error
    
    def execute_paypal_payment(self, payment_id, payer_id):
        """Execute PayPal payment after user approval"""
        payment = paypalrestsdk.Payment.find(payment_id)
        
        if payment.execute({'payer_id': payer_id}):
            # Record transaction
            transaction = PaymentTransaction.query.filter_by(
                transaction_id=payment_id
            ).first()
            
            if transaction:
                transaction.status = 'completed'
                transaction.completed_at = datetime.utcnow()
                transaction.gateway_response = json.dumps(payment.to_dict())
                
                # Update fee record
                if transaction.fee_id:
                    fee = Fee.query.get(transaction.fee_id)
                    fee.paid_amount += transaction.amount
                    fee.status = 'paid' if fee.paid_amount >= fee.amount else 'partial'
                    fee.payment_date = datetime.utcnow().date()
                    fee.transaction_id = payment_id
                    fee.payment_method = 'paypal'
                
                db.session.commit()
            
            return True, payment
        else:
            return False, payment.error
    
    def process_fee_payment(self, fee_id, user_id, amount, payment_method='stripe', metadata=None):
        """Process a fee payment"""
        fee = Fee.query.get(fee_id)
        if not fee:
            return None, "Fee not found"
        
        # Create transaction record
        transaction = PaymentTransaction(
            transaction_id=f"TXN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user_id}",
            fee_id=fee_id,
            user_id=user_id,
            amount=amount,
            currency='ZAR',
            payment_method=payment_method,
            status='pending',
            payment_gateway=payment_method
        )
        db.session.add(transaction)
        db.session.commit()
        
        if payment_method == 'stripe':
            result, error = self.create_stripe_payment_intent(
                amount,
                currency='zar',
                metadata={
                    'transaction_id': transaction.transaction_id,
                    'fee_id': str(fee_id),
                    'user_id': str(user_id),
                    **(metadata or {})
                }
            )
            
            if result:
                transaction.transaction_id = result['payment_intent_id']
                db.session.commit()
                return {
                    'payment_intent': result['client_secret'],
                    'transaction_id': transaction.transaction_id,
                    'amount': amount
                }, None
            
        elif payment_method == 'paypal':
            result, error = self.create_paypal_payment(
                amount,
                currency='ZAR',
                description=f"School Fees - {fee.fee_type}",
                metadata={
                    'transaction_id': transaction.transaction_id,
                    'fee_id': str(fee_id)
                }
            )
            
            if result:
                transaction.transaction_id = result['payment_id']
                db.session.commit()
                return result, None
        
        return None, error or "Payment processing failed"
    
    def handle_stripe_webhook(self, payload, signature):
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.stripe_webhook_secret
            )
            
            if event.type == 'payment_intent.succeeded':
                payment_intent = event.data.object
                self.confirm_stripe_payment(payment_intent.id)
                
            elif event.type == 'payment_intent.payment_failed':
                payment_intent = event.data.object
                transaction = PaymentTransaction.query.filter_by(
                    transaction_id=payment_intent.id
                ).first()
                
                if transaction:
                    transaction.status = 'failed'
                    transaction.gateway_response = json.dumps(event.data)
                    db.session.commit()
            
            return True, event.type
            
        except Exception as e:
            return False, str(e)
    
    def get_payment_history(self, user_id):
        """Get payment history for a user"""
        transactions = PaymentTransaction.query.filter_by(
            user_id=user_id
        ).order_by(PaymentTransaction.created_at.desc()).all()
        
        return [{
            'transaction_id': t.transaction_id,
            'amount': t.amount,
            'currency': t.currency,
            'payment_method': t.payment_method,
            'status': t.status,
            'created_at': t.created_at.isoformat(),
            'completed_at': t.completed_at.isoformat() if t.completed_at else None,
            'receipt_url': t.receipt_url
        } for t in transactions]
    
    def generate_receipt(self, transaction_id):
        """Generate receipt for payment"""
        transaction = PaymentTransaction.query.filter_by(
            transaction_id=transaction_id
        ).first()
        
        if not transaction:
            return None, "Transaction not found"
        
        # Generate PDF receipt using report service
        from report_service import ReportGenerator
        generator = ReportGenerator()
        
        receipt_data = {
            'transaction_id': transaction.transaction_id,
            'date': transaction.completed_at or transaction.created_at,
            'amount': transaction.amount,
            'payment_method': transaction.payment_method,
            'fee_details': None
        }
        
        if transaction.fee_id:
            fee = Fee.query.get(transaction.fee_id)
            learner = Learner.query.get(fee.learner_id)
            receipt_data['fee_details'] = {
                'type': fee.fee_type,
                'learner': learner.user.full_name,
                'grade': learner.grade,
                'academic_year': fee.academic_year,
                'term': fee.term
            }
        
        # Generate PDF
        filepath = generator.generate_payment_receipt(receipt_data)
        
        if filepath:
            transaction.receipt_url = filepath
            db.session.commit()
        
        return filepath, None