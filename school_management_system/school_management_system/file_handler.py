import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
from datetime import datetime
import magic

class FileHandler:
    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx',
        'ppt', 'pptx', 'zip', 'rar', 'mp4', 'mp3', 'csv', 'py', 'java', 'cpp'
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    def __init__(self, upload_folder='uploads'):
        self.upload_folder = upload_folder
        self.create_upload_folders()
    
    def create_upload_folders(self):
        """Create necessary upload folders"""
        folders = [
            self.upload_folder,
            os.path.join(self.upload_folder, 'assignments'),
            os.path.join(self.upload_folder, 'submissions'),
            os.path.join(self.upload_folder, 'profiles'),
            os.path.join(self.upload_folder, 'reports'),
            os.path.join(self.upload_folder, 'receipts'),
            os.path.join(self.upload_folder, 'temp')
        ]
        
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
    
    def allowed_file(self, filename):
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS
    
    def get_file_size(self, file):
        """Get file size"""
        file.seek(0, 2)  # Seek to end
        size = file.tell()
        file.seek(0)  # Reset position
        return size
    
    def save_file(self, file, subfolder='', custom_name=None):
        """Save uploaded file with unique name"""
        if not file or file.filename == '':
            return None, "No file selected"
        
        if not self.allowed_file(file.filename):
            return None, "File type not allowed"
        
        # Check file size
        size = self.get_file_size(file)
        if size > self.MAX_FILE_SIZE:
            return None, f"File too large. Maximum size is {self.MAX_FILE_SIZE // (1024*1024)}MB"
        
        # Generate filename
        if custom_name:
            filename = secure_filename(custom_name)
        else:
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
        
        # Determine save path
        if subfolder:
            save_path = os.path.join(self.upload_folder, subfolder, filename)
        else:
            save_path = os.path.join(self.upload_folder, filename)
        
        # Save file
        file.save(save_path)
        
        # Get file info
        file_info = {
            'filename': filename,
            'original_name': file.filename,
            'path': save_path,
            'size': size,
            'mime_type': magic.from_file(save_path, mime=True),
            'uploaded_at': datetime.utcnow().isoformat()
        }
        
        return file_info, None
    
    def save_assignment_file(self, file, assignment_id):
        """Save assignment attachment"""
        subfolder = f"assignments/{assignment_id}"
        os.makedirs(os.path.join(self.upload_folder, subfolder), exist_ok=True)
        return self.save_file(file, subfolder)
    
    def save_submission_file(self, file, submission_id):
        """Save student submission file"""
        subfolder = f"submissions/{submission_id}"
        os.makedirs(os.path.join(self.upload_folder, subfolder), exist_ok=True)
        return self.save_file(file, subfolder)
    
    def save_profile_picture(self, file, user_id):
        """Save and optimize profile picture"""
        subfolder = "profiles"
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"user_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
        save_path = os.path.join(self.upload_folder, subfolder, filename)
        
        # Save and optimize image
        img = Image.open(file)
        
        # Resize if too large
        if img.width > 500 or img.height > 500:
            img.thumbnail((500, 500), Image.Resampling.LANCZOS)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb_img
        
        # Save as JPEG
        jpeg_path = save_path.rsplit('.', 1)[0] + '.jpg'
        img.save(jpeg_path, 'JPEG', quality=85, optimize=True)
        
        return {
            'filename': os.path.basename(jpeg_path),
            'path': jpeg_path,
            'size': os.path.getsize(jpeg_path),
            'uploaded_at': datetime.utcnow().isoformat()
        }, None
    
    def save_receipt(self, file, payment_id):
        """Save payment receipt/proof"""
        subfolder = f"receipts/{payment_id}"
        os.makedirs(os.path.join(self.upload_folder, subfolder), exist_ok=True)
        return self.save_file(file, subfolder)
    
    def delete_file(self, filepath):
        """Delete file from filesystem"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            print(f"Error deleting file {filepath}: {e}")
        return False
    
    def get_file_url(self, filepath):
        """Get URL for file access"""
        if filepath.startswith(self.upload_folder):
            return filepath.replace(self.upload_folder, '/uploads')
        return None
    
    def scan_for_viruses(self, filepath):
        """Basic file scanning (placeholder for antivirus integration)"""
        # This is a placeholder. In production, integrate with ClamAV or similar
        suspicious_extensions = {'.exe', '.bat', '.cmd', '.sh', '.vbs', '.ps1'}
        
        if any(filepath.lower().endswith(ext) for ext in suspicious_extensions):
            return False, "Suspicious file type detected"
        
        return True, None