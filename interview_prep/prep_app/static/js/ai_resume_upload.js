/**
 * AI Resume Upload Page JavaScript
 * Handles file upload, validation, and preview functionality
 */

class AIResumeUploader {
    constructor() {
        this.fileInput = null;
        this.uploadArea = null;
        this.fileInfo = null;
        this.maxFileSize = 10 * 1024 * 1024; // 10MB
        this.allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
        this.allowedExtensions = ['.pdf', '.docx'];
        
        this.init();
    }

    init() {
        this.setupFileUpload();
        this.setupDragDrop();
        this.setupFormValidation();
    }

    setupFileUpload() {
        this.uploadArea = document.getElementById('file-upload-area');
        this.fileInput = this.uploadArea?.querySelector('.file-input');
        this.fileInfo = document.getElementById('file-info');

        if (!this.fileInput || !this.uploadArea) return;

        // Handle file selection
        this.fileInput.addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files[0]);
        });

        // Handle click on upload area with debounce
        let clickTimeout = null;
        this.uploadArea.addEventListener('click', (e) => {
            // Prevent multiple rapid clicks
            if (clickTimeout) return;
            
            // Only trigger if clicking on upload area, not file input itself
            if (e.target === this.fileInput) return;
            
            clickTimeout = setTimeout(() => {
                this.fileInput.click();
                clickTimeout = null;
            }, 100);
        });
    }

    setupDragDrop() {
        if (!this.uploadArea) return;

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            this.uploadArea.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });

        // Highlight upload area when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            this.uploadArea.addEventListener(eventName, () => {
                this.uploadArea.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            this.uploadArea.addEventListener(eventName, () => {
                this.uploadArea.classList.remove('dragover');
            }, false);
        });

        // Handle dropped files
        this.uploadArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileSelect(files[0]);
            }
        }, false);
    }

    setupFormValidation() {
        const form = document.getElementById('ai-resume-upload-form');
        if (!form) return;

        // Real-time validation
        const inputs = form.querySelectorAll('.form-input, .form-textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', () => {
                this.validateField(input);
            });
        });
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    handleFileSelect(file) {
        if (!file) return;

        // Validate file
        const validation = this.validateFile(file);
        if (!validation.valid) {
            this.showError(validation.error);
            // Don't clear file input immediately to prevent double dialog
            setTimeout(() => {
                this.fileInput.value = '';
            }, 500);
            return;
        }

        // Show file info
        this.displayFileInfo(file);
        this.uploadArea.classList.add('has-file');

        // Show preview section
        this.showPreview(file);
    }

    validateFile(file) {
        // Check file size
        if (file.size > this.maxFileSize) {
            return {
                valid: false,
                error: `File size (${this.formatFileSize(file.size)}) exceeds the 10MB limit.`
            };
        }

        // Check file type by extension
        const fileName = file.name.toLowerCase();
        const hasValidExtension = this.allowedExtensions.some(ext => fileName.endsWith(ext));
        
        if (!hasValidExtension) {
            return {
                valid: false,
                error: `Invalid file type. Only PDF and DOCX files are allowed. You uploaded: ${file.name}`
            };
        }

        // Check MIME type if available
        if (file.type && !this.allowedTypes.includes(file.type)) {
            return {
                valid: false,
                error: `Invalid file format detected. Only PDF and DOCX files are supported.`
            };
        }

        // Additional checks for file integrity
        if (file.size === 0) {
            return {
                valid: false,
                error: 'The selected file is empty or corrupted.'
            };
        }

        return { valid: true };
    }

    displayFileInfo(file) {
        if (!this.fileInfo) return;

        const fileName = this.fileInfo.querySelector('.file-name');
        const fileSize = this.fileInfo.querySelector('.file-size');

        if (fileName) fileName.textContent = file.name;
        if (fileSize) fileSize.textContent = this.formatFileSize(file.size);

        this.fileInfo.style.display = 'flex';
    }

    showPreview(file) {
        // Update job description preview
        const jobDescTextarea = document.querySelector('textarea[name="job_description"]');
        const jdPreview = document.getElementById('jd-preview');
        
        if (jobDescTextarea && jdPreview) {
            const jdText = jobDescTextarea.value.trim();
            if (jdText) {
                jdPreview.textContent = this.truncateText(jdText, 500);
            }
        }

        // Note: Resume text extraction will happen server-side
        // The preview will be populated after form submission and page reload
        
        const previewSection = document.getElementById('preview-section');
        if (previewSection && jobDescTextarea?.value.trim()) {
            previewSection.style.display = 'block';
        }
    }

    validateField(field) {
        const value = field.value.trim();
        const isRequired = field.hasAttribute('required') || field.classList.contains('required');
        
        // Remove existing error state
        field.classList.remove('error');
        const existingError = field.parentNode.querySelector('.error-text');
        if (existingError && !existingError.textContent.includes('This field is required')) {
            existingError.remove();
        }

        // Validate required fields
        if (isRequired && !value) {
            this.showFieldError(field, 'This field is required');
            return false;
        }

        // Validate job description length
        if (field.name === 'job_description' && value && value.length < 50) {
            this.showFieldError(field, 'Job description seems too short. Please provide more details.');
            return false;
        }

        // Validate job title
        if (field.name === 'job_title' && value && value.length < 3) {
            this.showFieldError(field, 'Job title seems too short.');
            return false;
        }

        return true;
    }

    showFieldError(field, message) {
        field.classList.add('error');
        
        // Don't add error if one already exists
        if (field.parentNode.querySelector('.error-text')) return;
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-text';
        errorDiv.textContent = message;
        field.parentNode.appendChild(errorDiv);
    }

    showError(message) {
        const modal = document.getElementById('error-modal');
        const messageEl = document.getElementById('error-message');
        
        if (modal && messageEl) {
            messageEl.textContent = message;
            modal.style.display = 'flex';
        } else {
            alert(message); // Fallback
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    }

    // Public methods for external use
    removeFile() {
        if (this.fileInput) {
            this.fileInput.value = '';
        }
        if (this.fileInfo) {
            this.fileInfo.style.display = 'none';
        }
        if (this.uploadArea) {
            this.uploadArea.classList.remove('has-file');
        }
        
        const previewSection = document.getElementById('preview-section');
        if (previewSection) {
            previewSection.style.display = 'none';
        }
    }

    validateForm() {
        const form = document.getElementById('ai-resume-upload-form');
        if (!form) return false;

        let isValid = true;

        // Validate required fields
        const requiredFields = form.querySelectorAll('input[required], textarea[required], .required');
        requiredFields.forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });

        // Validate file upload
        if (!this.fileInput || !this.fileInput.files[0]) {
            this.showError('Please upload your resume file');
            isValid = false;
        }

        return isValid;
    }
}

// Global functions for template use
function removeFile() {
    if (window.aiResumeUploader) {
        window.aiResumeUploader.removeFile();
    }
}

function closeErrorModal() {
    const modal = document.getElementById('error-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Auto-update job description preview
document.addEventListener('DOMContentLoaded', function() {
    const jobDescTextarea = document.querySelector('textarea[name="job_description"]');
    const jdPreview = document.getElementById('jd-preview');
    
    if (jobDescTextarea && jdPreview) {
        jobDescTextarea.addEventListener('input', function() {
            const text = this.value.trim();
            if (text) {
                jdPreview.textContent = text.length > 500 ? text.substr(0, 500) + '...' : text;
                
                // Show preview section if file is also present
                const fileInput = document.querySelector('.file-input');
                if (fileInput && fileInput.files[0]) {
                    document.getElementById('preview-section').style.display = 'block';
                }
            } else {
                document.getElementById('preview-section').style.display = 'none';
            }
        });
    }

    // Store uploader instance globally for template access
    window.aiResumeUploader = new AIResumeUploader();
});