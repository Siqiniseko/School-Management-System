import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import nltk
from nltk.tokenize import sent_tokenize
import PyPDF2
import docx
import requests
from bs4 import BeautifulSoup
import re
from models import db, PlagiarismCheck, Submission, Assignment
import json
import os

# Download NLTK data
nltk.download('punkt', quiet=True)

class PlagiarismDetector:
    def __init__(self):
        # Initialize sentence transformer for semantic similarity
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
        
        # AI detection keywords
        self.ai_indicators = [
            'as an ai', 'i cannot', 'i don\'t have', 'as a language model',
            'it is important to note', 'however, it is crucial',
            'in conclusion', 'firstly', 'secondly', 'thirdly', 'lastly',
            'it is worth mentioning', 'one could argue'
        ]
    
    def extract_text_from_file(self, filepath):
        """Extract text from various file formats"""
        text = ""
        
        try:
            if filepath.endswith('.pdf'):
                with open(filepath, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text()
            
            elif filepath.endswith('.docx'):
                doc = docx.Document(filepath)
                for para in doc.paragraphs:
                    text += para.text + "\n"
            
            elif filepath.endswith('.txt'):
                with open(filepath, 'r', encoding='utf-8') as file:
                    text = file.read()
            
            else:
                # Try to read as plain text
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
                    text = file.read()
        
        except Exception as e:
            print(f"Error extracting text: {e}")
        
        return self.clean_text(text)
    
    def clean_text(self, text):
        """Clean and preprocess text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\-\']', '', text)
        return text.strip()
    
    def check_internal_plagiarism(self, submission_text, assignment_id):
        """Check plagiarism against other submissions for the same assignment"""
        # Get all submissions for this assignment
        other_submissions = Submission.query.filter(
            Submission.assignment_id == assignment_id,
            Submission.files.isnot(None)
        ).all()
        
        if not other_submissions:
            return {'similarity_score': 0, 'matches': []}
        
        # Prepare corpus
        corpus = []
        submission_map = {}
        
        for i, sub in enumerate(other_submissions):
            # Extract text from files
            files = json.loads(sub.files) if sub.files else []
            sub_text = ""
            for file in files:
                sub_text += self.extract_text_from_file(file) + " "
            
            if sub_text.strip():
                corpus.append(sub_text)
                submission_map[i] = sub.id
        
        if not corpus:
            return {'similarity_score': 0, 'matches': []}
        
        # Add submission text to corpus
        corpus.append(submission_text)
        
        # Calculate TF-IDF similarity
        tfidf_matrix = self.vectorizer.fit_transform(corpus)
        similarity_matrix = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])
        
        # Find matches
        matches = []
        max_similarity = 0
        
        for i, score in enumerate(similarity_matrix[0]):
            if score > 0.3:  # Threshold for similarity
                matches.append({
                    'submission_id': submission_map[i],
                    'similarity_score': round(score * 100, 2)
                })
                max_similarity = max(max_similarity, score)
        
        return {
            'similarity_score': round(max_similarity * 100, 2),
            'matches': matches
        }
    
    def check_web_plagiarism(self, text, num_results=10):
        """Check plagiarism against web sources using search"""
        # Split text into sentences
        sentences = sent_tokenize(text)
        
        # Select key sentences (longer sentences likely to contain unique content)
        key_sentences = [s for s in sentences if len(s.split()) > 10][:5]
        
        matches = []
        
        for sentence in key_sentences:
            # Search Google (using a simple search API simulation)
            # In production, use Google Custom Search API
            search_results = self.search_web(sentence)
            
            for result in search_results:
                similarity = self.calculate_text_similarity(sentence, result['snippet'])
                if similarity > 0.3:
                    matches.append({
                        'source': result['title'],
                        'url': result['url'],
                        'matched_text': sentence[:100] + "...",
                        'similarity': round(similarity * 100, 2)
                    })
        
        return matches[:num_results]
    
    def search_web(self, query):
        """Simulate web search - replace with actual search API in production"""
        # This is a placeholder. In production, use:
        # - Google Custom Search API
        # - Bing Search API
        # - DuckDuckGo API
        
        # For demo, return empty results
        return []
    
    def detect_ai_generated_content(self, text):
        """Detect if content is likely AI-generated"""
        indicators_found = []
        ai_score = 0
        
        # Check for AI indicator phrases
        text_lower = text.lower()
        for indicator in self.ai_indicators:
            if indicator in text_lower:
                indicators_found.append(indicator)
                ai_score += 10
        
        # Check sentence structure patterns
        sentences = sent_tokenize(text)
        
        # AI-generated text often has consistent sentence length
        if len(sentences) > 5:
            lengths = [len(s.split()) for s in sentences]
            std_dev = np.std(lengths)
            if std_dev < 5:  # Very consistent sentence length
                ai_score += 15
                indicators_found.append("Consistent sentence length pattern")
        
        # Check for overuse of transition words
        transition_words = ['however', 'therefore', 'furthermore', 'moreover', 'consequently']
        transition_count = sum(text_lower.count(word) for word in transition_words)
        if transition_count > len(sentences) * 0.5:
            ai_score += 10
            indicators_found.append("High transition word frequency")
        
        # Check for repetitive structure
        if 'firstly' in text_lower and 'secondly' in text_lower and 'thirdly' in text_lower:
            ai_score += 15
            indicators_found.append("Numbered point structure")
        
        # Semantic consistency analysis
        embeddings = self.model.encode(sentences[:10])  # First 10 sentences
        if len(embeddings) > 1:
            similarities = cosine_similarity(embeddings[:-1], embeddings[1:])
            avg_similarity = np.mean([s[0] for s in similarities])
            if avg_similarity > 0.8:  # Very consistent semantically
                ai_score += 10
                indicators_found.append("High semantic consistency")
        
        # Calculate probability
        ai_probability = min(95, ai_score)
        
        return {
            'ai_probability': ai_probability,
            'indicators': indicators_found,
            'is_likely_ai': ai_probability > 60
        }
    
    def calculate_text_similarity(self, text1, text2):
        """Calculate semantic similarity between two texts"""
        embeddings = self.model.encode([text1, text2])
        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        return similarity
    
    def analyze_submission(self, submission_id):
        """Perform complete plagiarism analysis on a submission"""
        submission = Submission.query.get(submission_id)
        if not submission or not submission.files:
            return None, "No files to analyze"
        
        # Check if already analyzed
        existing_check = PlagiarismCheck.query.filter_by(
            submission_id=submission_id
        ).first()
        
        if existing_check:
            return existing_check, None
        
        # Extract text from all files
        files = json.loads(submission.files)
        full_text = ""
        for file in files:
            full_text += self.extract_text_from_file(file) + "\n"
        
        if not full_text.strip():
            return None, "No text content found"
        
        # Perform checks
        internal_result = self.check_internal_plagiarism(full_text, submission.assignment_id)
        web_result = self.check_web_plagiarism(full_text)
        ai_result = self.detect_ai_generated_content(full_text)
        
        # Combine results
        overall_similarity = max(
            internal_result['similarity_score'],
            max([m['similarity'] for m in web_result]) if web_result else 0
        )
        
        # Create plagiarism check record
        check = PlagiarismCheck(
            submission_id=submission_id,
            similarity_score=overall_similarity,
            matched_sources=json.dumps({
                'internal': internal_result['matches'],
                'web': web_result
            }),
            ai_generated_probability=ai_result['ai_probability'],
            detailed_report=json.dumps({
                'internal_similarity': internal_result['similarity_score'],
                'web_matches': len(web_result),
                'ai_indicators': ai_result['indicators'],
                'text_length': len(full_text),
                'analyzed_at': datetime.utcnow().isoformat()
            }),
            status='completed'
        )
        
        db.session.add(check)
        db.session.commit()
        
        return check, None
    
    def get_plagiarism_report(self, submission_id):
        """Generate detailed plagiarism report"""
        check = PlagiarismCheck.query.filter_by(
            submission_id=submission_id
        ).first()
        
        if not check:
            return None
        
        report = {
            'submission_id': submission_id,
            'overall_similarity': check.similarity_score,
            'ai_probability': check.ai_generated_probability,
            'status': check.status,
            'checked_at': check.checked_at.isoformat(),
            'details': json.loads(check.detailed_report) if check.detailed_report else {},
            'matches': json.loads(check.matched_sources) if check.matched_sources else {}
        }
        
        # Add risk assessment
        if check.similarity_score > 50:
            report['risk_level'] = 'high'
            report['recommendation'] = 'Significant similarity detected. Manual review required.'
        elif check.similarity_score > 30:
            report['risk_level'] = 'medium'
            report['recommendation'] = 'Moderate similarity detected. Review recommended.'
        else:
            report['risk_level'] = 'low'
            report['recommendation'] = 'No significant issues detected.'
        
        if check.ai_generated_probability > 70:
            report['ai_risk'] = 'high'
            report['ai_recommendation'] = 'Content appears to be AI-generated. Verify originality.'
        elif check.ai_generated_probability > 40:
            report['ai_risk'] = 'medium'
            report['ai_recommendation'] = 'Some indicators of AI generation detected.'
        
        return report