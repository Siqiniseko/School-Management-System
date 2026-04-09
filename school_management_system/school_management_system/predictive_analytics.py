import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, mean_squared_error, classification_report
import joblib
from models import db, Learner, Grade, Attendance, Fee, PredictiveModel, StudentPrediction
from datetime import datetime, timedelta
import json
import pickle

class PredictiveAnalytics:
    def __init__(self):
        self.models = {}
        self.load_models()
    
    def load_models(self):
        """Load trained models from database"""
        active_models = PredictiveModel.query.filter_by(is_active=True).all()
        
        for model_record in active_models:
            try:
                model = pickle.loads(model_record.model_data)
                self.models[model_record.model_name] = {
                    'model': model,
                    'metadata': {
                        'accuracy': model_record.accuracy,
                        'last_trained': model_record.last_trained,
                        'features': json.loads(model_record.features_used)
                    }
                }
            except Exception as e:
                print(f"Error loading model {model_record.model_name}: {e}")
    
    def prepare_learner_features(self, learner_id):
        """Prepare feature vector for a learner"""
        learner = Learner.query.get(learner_id)
        if not learner:
            return None
        
        features = {}
        
        # Academic features
        grades = Grade.query.filter_by(learner_id=learner_id).all()
        if grades:
            scores = [g.score / g.max_score * 100 for g in grades]
            features['avg_grade'] = np.mean(scores)
            features['std_grade'] = np.std(scores)
            features['min_grade'] = np.min(scores)
            features['max_grade'] = np.max(scores)
            
            # Grade trend
            if len(scores) > 2:
                recent_avg = np.mean(scores[-3:])
                older_avg = np.mean(scores[:-3]) if len(scores) > 3 else recent_avg
                features['grade_trend'] = recent_avg - older_avg
            else:
                features['grade_trend'] = 0
        else:
            features['avg_grade'] = 0
            features['std_grade'] = 0
            features['min_grade'] = 0
            features['max_grade'] = 0
            features['grade_trend'] = 0
        
        # Attendance features
        attendance_records = Attendance.query.filter_by(learner_id=learner_id).all()
        if attendance_records:
            present = sum(1 for a in attendance_records if a.status == 'present')
            late = sum(1 for a in attendance_records if a.status == 'late')
            absent = sum(1 for a in attendance_records if a.status == 'absent')
            total = len(attendance_records)
            
            features['attendance_rate'] = (present / total * 100) if total > 0 else 0
            features['late_rate'] = (late / total * 100) if total > 0 else 0
            features['absent_rate'] = (absent / total * 100) if total > 0 else 0
            
            # Recent attendance trend (last 30 days)
            thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
            recent_records = [a for a in attendance_records if a.date >= thirty_days_ago]
            if recent_records:
                recent_present = sum(1 for a in recent_records if a.status == 'present')
                features['recent_attendance'] = (recent_present / len(recent_records) * 100)
            else:
                features['recent_attendance'] = features['attendance_rate']
        else:
            features['attendance_rate'] = 100
            features['late_rate'] = 0
            features['absent_rate'] = 0
            features['recent_attendance'] = 100
        
        # Fee payment behavior
        fees = Fee.query.filter_by(learner_id=learner_id).all()
        if fees:
            total_fees = sum(f.amount for f in fees)
            paid_fees = sum(f.paid_amount for f in fees)
            features['fee_payment_rate'] = (paid_fees / total_fees * 100) if total_fees > 0 else 100
            
            # On-time payment rate
            on_time = sum(1 for f in fees if f.paid_amount > 0 and f.payment_date and f.payment_date <= f.due_date)
            features['on_time_payment_rate'] = (on_time / len(fees) * 100) if fees else 100
        else:
            features['fee_payment_rate'] = 100
            features['on_time_payment_rate'] = 100
        
        # Demographic features
        features['grade_level'] = learner.grade
        features['days_enrolled'] = (datetime.utcnow().date() - learner.enrollment_date).days if learner.enrollment_date else 0
        
        return features
    
    def predict_performance(self, learner_id, subject_id=None):
        """Predict future academic performance"""
        features = self.prepare_learner_features(learner_id)
        if not features:
            return None, "Unable to prepare features"
        
        # Get or train model
        model_name = 'performance_predictor'
        if model_name not in self.models:
            self.train_performance_model()
        
        if model_name not in self.models:
            return None, "Model not available"
        
        model_info = self.models[model_name]
        model = model_info['model']
        
        # Prepare feature vector
        feature_vector = self.create_feature_vector(features, model_info['metadata']['features'])
        
        # Make prediction
        prediction = model.predict([feature_vector])[0]
        
        # Calculate confidence
        confidence = self.calculate_prediction_confidence(model, [feature_vector])
        
        # Save prediction
        student_prediction = StudentPrediction(
            learner_id=learner_id,
            prediction_type='performance',
            predicted_value=float(prediction),
            confidence=confidence,
            factors=json.dumps(self.get_influential_factors(features, prediction)),
            model_version=model_name
        )
        db.session.add(student_prediction)
        db.session.commit()
        
        return {
            'predicted_score': round(prediction, 1),
            'confidence': round(confidence, 1),
            'factors': self.get_influential_factors(features, prediction)
        }, None
    
    def predict_dropout_risk(self, learner_id):
        """Predict student dropout risk"""
        features = self.prepare_learner_features(learner_id)
        if not features:
            return None, "Unable to prepare features"
        
        model_name = 'dropout_risk_classifier'
        if model_name not in self.models:
            self.train_dropout_model()
        
        if model_name not in self.models:
            return None, "Model not available"
        
        model_info = self.models[model_name]
        model = model_info['model']
        
        feature_vector = self.create_feature_vector(features, model_info['metadata']['features'])
        
        # Get probability scores
        probabilities = model.predict_proba([feature_vector])[0]
        risk_level = model.predict([feature_vector])[0]
        
        risk_categories = ['Low', 'Medium', 'High']
        risk_label = risk_categories[risk_level]
        risk_probability = probabilities[risk_level]
        
        # Get contributing factors
        factors = self.get_risk_factors(features, risk_label)
        
        # Save prediction
        student_prediction = StudentPrediction(
            learner_id=learner_id,
            prediction_type='dropout_risk',
            predicted_value=risk_level,
            confidence=risk_probability * 100,
            factors=json.dumps(factors),
            model_version=model_name
        )
        db.session.add(student_prediction)
        db.session.commit()
        
        return {
            'risk_level': risk_label,
            'probability': round(risk_probability * 100, 1),
            'factors': factors,
            'recommendations': self.get_intervention_recommendations(risk_label, factors)
        }, None
    
    def train_performance_model(self):
        """Train academic performance prediction model"""
        # Collect training data
        learners = Learner.query.all()
        X = []
        y = []
        feature_names = []
        
        for learner in learners:
            features = self.prepare_learner_features(learner.id)
            if features:
                # Get actual performance (average of next 3 grades)
                future_grades = Grade.query.filter(
                    Grade.learner_id == learner.id,
                    Grade.date > datetime.utcnow().date() - timedelta(days=90)
                ).limit(3).all()
                
                if future_grades:
                    avg_future_grade = np.mean([g.score / g.max_score * 100 for g in future_grades])
                    
                    if not feature_names:
                        feature_names = list(features.keys())
                    
                    X.append([features[name] for name in feature_names])
                    y.append(avg_future_grade)
        
        if len(X) < 10:
            return False, "Insufficient training data"
        
        X = np.array(X)
        y = np.array(y)
        
        # Train model
        model = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X, y)
        
        # Evaluate
        score = model.score(X, y)
        
        # Save model
        model_data = pickle.dumps(model)
        
        predictive_model = PredictiveModel.query.filter_by(
            model_name='performance_predictor'
        ).first()
        
        if predictive_model:
            predictive_model.model_data = model_data
            predictive_model.accuracy = score
            predictive_model.last_trained = datetime.utcnow()
            predictive_model.features_used = json.dumps(feature_names)
        else:
            predictive_model = PredictiveModel(
                model_name='performance_predictor',
                model_type='regression',
                model_data=model_data,
                accuracy=score,
                last_trained=datetime.utcnow(),
                features_used=json.dumps(feature_names),
                is_active=True
            )
            db.session.add(predictive_model)
        
        db.session.commit()
        
        # Load into memory
        self.models['performance_predictor'] = {
            'model': model,
            'metadata': {
                'accuracy': score,
                'last_trained': datetime.utcnow(),
                'features': feature_names
            }
        }
        
        return True, f"Model trained with accuracy: {score:.3f}"
    
    def train_dropout_model(self):
        """Train dropout risk prediction model"""
        learners = Learner.query.all()
        X = []
        y = []
        feature_names = []
        
        for learner in learners:
            features = self.prepare_learner_features(learner.id)
            if features:
                # Define dropout risk (simplified - in production use actual data)
                risk = 0  # Low risk
                if features['attendance_rate'] < 75:
                    risk = 2  # High risk
                elif features['attendance_rate'] < 85:
                    risk = 1  # Medium risk
                
                if not feature_names:
                    feature_names = list(features.keys())
                
                X.append([features[name] for name in feature_names])
                y.append(risk)
        
        if len(X) < 10:
            return False, "Insufficient training data"
        
        X = np.array(X)
        y = np.array(y)
        
        # Train model
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        # Evaluate
        score = accuracy_score(y, model.predict(X))
        
        # Save model
        model_data = pickle.dumps(model)
        
        predictive_model = PredictiveModel.query.filter_by(
            model_name='dropout_risk_classifier'
        ).first()
        
        if predictive_model:
            predictive_model.model_data = model_data
            predictive_model.accuracy = score
            predictive_model.last_trained = datetime.utcnow()
            predictive_model.features_used = json.dumps(feature_names)
        else:
            predictive_model = PredictiveModel(
                model_name='dropout_risk_classifier',
                model_type='classification',
                model_data=model_data,
                accuracy=score,
                last_trained=datetime.utcnow(),
                features_used=json.dumps(feature_names),
                is_active=True
            )
            db.session.add(predictive_model)
        
        db.session.commit()
        
        # Load into memory
        self.models['dropout_risk_classifier'] = {
            'model': model,
            'metadata': {
                'accuracy': score,
                'last_trained': datetime.utcnow(),
                'features': feature_names
            }
        }
        
        return True, f"Model trained with accuracy: {score:.3f}"
    
    def create_feature_vector(self, features, feature_names):
        """Create feature vector from features dictionary"""
        return [features.get(name, 0) for name in feature_names]
    
    def calculate_prediction_confidence(self, model, X):
        """Calculate confidence of prediction"""
        # For ensemble models, use standard deviation of predictions
        if hasattr(model, 'estimators_'):
            predictions = np.array([est.predict(X) for est in model.estimators_])
            std_dev = np.std(predictions)
            confidence = 100 - min(50, std_dev * 10)  # Lower std = higher confidence
        else:
            confidence = 80  # Default confidence
        
        return confidence
    
    def get_influential_factors(self, features, prediction):
        """Identify factors most influencing the prediction"""
        factors = []
        
        if features.get('attendance_rate', 100) < 85:
            factors.append({
                'factor': 'Low attendance',
                'impact': 'negative',
                'current_value': round(features['attendance_rate'], 1),
                'recommendation': 'Improve attendance to boost performance'
            })
        
        if features.get('grade_trend', 0) < -5:
            factors.append({
                'factor': 'Declining grades',
                'impact': 'negative',
                'current_value': round(features['grade_trend'], 1),
                'recommendation': 'Seek additional academic support'
            })
        
        if features.get('avg_grade', 0) > 80:
            factors.append({
                'factor': 'Strong academic performance',
                'impact': 'positive',
                'current_value': round(features['avg_grade'], 1),
                'recommendation': 'Continue excellent work'
            })
        
        if features.get('fee_payment_rate', 100) < 90:
            factors.append({
                'factor': 'Fee payment delays',
                'impact': 'neutral',
                'current_value': round(features['fee_payment_rate'], 1),
                'recommendation': 'Address outstanding fees'
            })
        
        return factors
    
    def get_risk_factors(self, features, risk_level):
        """Get factors contributing to risk level"""
        factors = []
        
        if risk_level != 'Low':
            if features.get('attendance_rate', 100) < 80:
                factors.append({
                    'factor': 'Poor attendance',
                    'value': f"{features['attendance_rate']:.1f}%",
                    'threshold': '80%'
                })
            
            if features.get('avg_grade', 0) < 50:
                factors.append({
                    'factor': 'Low academic performance',
                    'value': f"{features['avg_grade']:.1f}%",
                    'threshold': '50%'
                })
            
            if features.get('late_rate', 0) > 20:
                factors.append({
                    'factor': 'Frequent tardiness',
                    'value': f"{features['late_rate']:.1f}%",
                    'threshold': '20%'
                })
        
        return factors
    
    def get_intervention_recommendations(self, risk_level, factors):
        """Get intervention recommendations based on risk level"""
        recommendations = []
        
        if risk_level == 'High':
            recommendations = [
                "Schedule immediate parent-teacher conference",
                "Assign academic mentor or tutor",
                "Implement daily attendance monitoring",
                "Consider counseling services referral"
            ]
        elif risk_level == 'Medium':
            recommendations = [
                "Monitor attendance weekly",
                "Provide additional academic support in struggling subjects",
                "Send progress reports to parents bi-weekly"
            ]
        else:
            recommendations = [
                "Continue regular monitoring",
                "Encourage participation in enrichment activities"
            ]
        
        return recommendations
    
    def generate_class_predictions(self, class_id):
        """Generate predictions for entire class"""
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return None
        
        learners = class_obj.learners.all()
        predictions = []
        
        for learner in learners:
            perf_pred, _ = self.predict_performance(learner.id)
            risk_pred, _ = self.predict_dropout_risk(learner.id)
            
            predictions.append({
                'learner_id': learner.id,
                'name': learner.user.full_name,
                'predicted_score': perf_pred['predicted_score'] if perf_pred else None,
                'dropout_risk': risk_pred['risk_level'] if risk_pred else None,
                'risk_probability': risk_pred['probability'] if risk_pred else None
            })
        
        return predictions
    
    def get_analytics_insights(self):
        """Generate AI-powered insights for administrators"""
        insights = []
        
        # Analyze school-wide trends
        all_learners = Learner.query.all()
        predictions = []
        
        for learner in all_learners[:50]:  # Sample for performance
            pred, _ = self.predict_performance(learner.id)
            if pred:
                predictions.append(pred['predicted_score'])
        
        if predictions:
            avg_predicted = np.mean(predictions)
            if avg_predicted < 65:
                insights.append({
                    'type': 'academic',
                    'severity': 'high',
                    'message': f"School-wide predicted average is {avg_predicted:.1f}%. Academic intervention may be needed.",
                    'action': 'Review curriculum and teaching strategies'
                })
        
        # Check attendance patterns
        attendance_rate = db.session.query(
            func.avg(
                db.case(
                    (Attendance.status == 'present', 100),
                    else_=0
                )
            )
        ).filter(
            Attendance.date >= datetime.utcnow().date() - timedelta(days=30)
        ).scalar()
        
        if attendance_rate and attendance_rate < 85:
            insights.append({
                'type': 'attendance',
                'severity': 'medium',
                'message': f"Average attendance rate is {attendance_rate:.1f}% over the last 30 days.",
                'action': 'Implement attendance improvement initiatives'
            })
        
        return insights