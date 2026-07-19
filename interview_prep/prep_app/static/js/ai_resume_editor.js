/**
 * AI Resume Editor - Live Preview Template Style Editor
 * Handles editing of resume data with real-time A4 preview updates
 * Compatible with the live preview template design
 */

class AIResumeEditor {
    constructor(previewContainerId, initialResumeData = {}, aiResult = {}) {
        this.previewContainer = previewContainerId;
        this.resumeData = this.initializeResumeData(initialResumeData);
        this.aiResult = aiResult;
        this.preview = null;
        
        this.init();
    }

    init() {
        // Initialize preview using the live template approach
        this.preview = new AIResumePreview(this.previewContainer);
        
        // Setup simplified form bindings matching live template
        this.setupFormBindings();
        
        // Setup simplified skills editor
        this.setupSkillsEditor();
        
        // Setup dynamic entries (experience/projects)
        this.setupDynamicEntries();
        
        // Load initial data
        this.loadResumeData(this.resumeData);
        
        // Initial preview render
        this.updatePreview();
    }

    initializeResumeData(data) {
        // Initialize data structure matching live template
        return {
            name: data.name || '',
            role: data.role || '',
            email: data.email || '',
            phone: data.phone || '',
            location: data.location || '',
            github: data.github || '',
            website: data.website || '',
            summary: data.summary || '',
            skills: {
                programming: (data.skills && data.skills.programming) || '',
                database: (data.skills && data.skills.database) || '',
                aiml: (data.skills && data.skills.aiml) || '',
                tools: (data.skills && data.tools) || '',
                soft: (data.skills && data.skills.soft) || '',
                additional: (data.skills && data.skills.additional) || ''
            },
            education: {
                degree: (data.education && data.education.degree) || '',
                institution: (data.education && data.education.institution) || '',
                dates: (data.education && data.education.dates) || '',
                loc: (data.education && data.education.loc) || ''
            },
            experience: Array.isArray(data.experience) ? data.experience : [],
            projects: Array.isArray(data.projects) ? data.projects : []
        };
    }

    setupFormBindings() {
        // Personal information - matching live template field names
        this.bindInput('#name', 'name');
        this.bindInput('#role', 'role');
        
        // Contact information - matching live template layout
        this.bindInput('#email', 'email');
        this.bindInput('#phone', 'phone');
        this.bindInput('#location', 'location');
        this.bindInput('#github', 'github');
        this.bindInput('#website', 'website');
        
        // Summary
        this.bindInput('#summary', 'summary');
        
        // Education
        this.bindInput('#edu_degree', 'education.degree');
        this.bindInput('#edu_institution', 'education.institution');
        this.bindInput('#edu_dates', 'education.dates');
        this.bindInput('#edu_loc', 'education.loc');
    }

    bindInput(selector, dataPath) {
        const element = document.querySelector(selector);
        if (!element) return;

        element.addEventListener('input', () => {
            this.setNestedValue(this.resumeData, dataPath, element.value);
            this.updatePreview();
        });
    }

    setupSkillsEditor() {
        // Simplified skills editor matching live template - just comma-separated text inputs
        this.bindInput('#skills_programming', 'skills.programming');
        this.bindInput('#skills_database', 'skills.database');
        this.bindInput('#skills_aiml', 'skills.aiml');
        this.bindInput('#skills_tools', 'skills.tools');
        this.bindInput('#skills_soft', 'skills.soft');
        this.bindInput('#skills_additional', 'skills.additional');
    }

    setupDynamicEntries() {
        // Initialize experience and projects containers
        this.renderExperienceEntries();
        this.renderProjectEntries();
    }

    renderExperienceEntries() {
        const container = document.querySelector('#exp');
        if (!container) return;
        
        container.innerHTML = this.resumeData.experience.map((exp, i) => `
            <div style="border:1px solid var(--border); background:#fff; border-radius:8px; padding:12px; margin:8px 0;">
                <div class="row"><label>Experience ${i+1} – Title</label><input type="text" value="${this.escapeHtml(exp.title || '')}" oninput="window.resumeEditor.updateExperienceField(${i},'title',this.value)" /></div>
                <div class="row"><label>Experience ${i+1} – Date (right)</label><input type="text" value="${this.escapeHtml(exp.date || '')}" oninput="window.resumeEditor.updateExperienceField(${i},'date',this.value)" /></div>
                <div class="row"><label>Experience ${i+1} – Bullets</label><textarea oninput="window.resumeEditor.updateExperienceField(${i},'bullets',this.value)" placeholder="One bullet per line">${this.escapeHtml(exp.bullets || '')}</textarea></div>
                <div class="controls"><button type="button" onclick="window.resumeEditor.removeExperienceEntry(${i})">Remove</button></div>
            </div>
        `).join('');
    }

    renderProjectEntries() {
        const container = document.querySelector('#proj');
        if (!container) return;
        
        container.innerHTML = this.resumeData.projects.map((proj, i) => `
            <div style="border:1px solid var(--border); background:#fff; border-radius:8px; padding:12px; margin:8px 0;">
                <div class="row"><label>Project ${i+1} – Title</label><input type="text" value="${this.escapeHtml(proj.title || '')}" oninput="window.resumeEditor.updateProjectField(${i},'title',this.value)" /></div>
                <div class="row"><label>Project ${i+1} – Date (right)</label><input type="text" value="${this.escapeHtml(proj.date || '')}" oninput="window.resumeEditor.updateProjectField(${i},'date',this.value)" /></div>
                <div class="row"><label>Project ${i+1} – Bullets</label><textarea oninput="window.resumeEditor.updateProjectField(${i},'bullets',this.value)" placeholder="One bullet per line">${this.escapeHtml(proj.bullets || '')}</textarea></div>
                <div class="controls"><button type="button" onclick="window.resumeEditor.removeProjectEntry(${i})">Remove</button></div>
            </div>
        `).join('');
    }

    // Experience management - simplified for live template style
    addExp() {
        if (this.resumeData.experience.length >= 3) return;
        this.resumeData.experience.push({title:'', date:'', bullets:''});
        this.renderExperienceEntries();
        this.updatePreview();
    }

    removeExperienceEntry(index) {
        this.resumeData.experience.splice(index, 1);
        this.renderExperienceEntries();
        this.updatePreview();
    }

    updateExperienceField(index, field, value) {
        if (this.resumeData.experience[index]) {
            this.resumeData.experience[index][field] = value;
            this.updatePreview();
        }
    }

    // Projects management - simplified for live template style  
    addProj() {
        if (this.resumeData.projects.length >= 3) return;
        this.resumeData.projects.push({title:'', date:'', bullets:''});
        this.renderProjectEntries();
        this.updatePreview();
    }

    removeProjectEntry(index) {
        this.resumeData.projects.splice(index, 1);
        this.renderProjectEntries();
        this.updatePreview();
    }

    updateProjectField(index, field, value) {
        if (this.resumeData.projects[index]) {
            this.resumeData.projects[index][field] = value;
            this.updatePreview();
        }
    }

    addSkill(category, skill) {
        if (!this.resumeData.skills[category]) {
            this.resumeData.skills[category] = [];
        }

        // Avoid duplicates
        if (!this.resumeData.skills[category].includes(skill)) {
            this.resumeData.skills[category].push(skill);
            this.renderSkillTags(category);
            this.updatePreview();
        }
    }

    removeSkill(category, skill) {
        if (this.resumeData.skills[category]) {
            this.resumeData.skills[category] = this.resumeData.skills[category].filter(s => s !== skill);
            this.renderSkillTags(category);
            this.updatePreview();
        }
    }

    renderSkillTags(category) {
        const categoryMapping = {
            'programming': 'programming',
            'database': 'database',
            'ai_ml_tools': 'ai-ml',
            'tools_methodologies': 'tools',
            'soft_skills': 'soft',
            'additional': 'additional'
        };

        const displayCategory = categoryMapping[category];
        if (!displayCategory) return;

        const container = document.querySelector(`#skills-${displayCategory}-tags`);
        if (!container) return;

        const skills = this.resumeData.skills[category] || [];
        
        container.innerHTML = skills.map(skill => `
            <div class="skill-tag">
                <span>${this.escapeHtml(skill)}</span>
                <button type="button" class="skill-tag-remove" onclick="window.resumeEditor.removeSkill('${category}', '${this.escapeHtml(skill)}')">×</button>
            </div>
        `).join('');
    }

    // Education management
    addEducation() {
        const education = {
            degree_bold: '',
            institution_bold: '',
            dates_left: '',
            location_right: ''
        };
        
        this.resumeData.education.push(education);
        this.renderEducationList();
        this.updatePreview();
    }

    removeEducation(index) {
        this.resumeData.education.splice(index, 1);
        this.renderEducationList();
        this.updatePreview();
    }

    renderEducationList() {
        const container = document.querySelector('#education-list');
        if (!container) return;

        container.innerHTML = this.resumeData.education.map((edu, index) => `
            <div class="entry-item">
                <div class="entry-header">
                    <h4>Education ${index + 1}</h4>
                    <div class="entry-controls">
                        <button type="button" class="btn btn-danger btn-sm" onclick="window.resumeEditor.removeEducation(${index})">Remove</button>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Degree</label>
                        <input type="text" class="form-control" value="${this.escapeHtml(edu.degree_bold)}" 
                               onchange="window.resumeEditor.updateEducation(${index}, 'degree_bold', this.value)">
                    </div>
                    <div class="form-group">
                        <label>Institution</label>
                        <input type="text" class="form-control" value="${this.escapeHtml(edu.institution_bold)}" 
                               onchange="window.resumeEditor.updateEducation(${index}, 'institution_bold', this.value)">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Dates</label>
                        <input type="text" class="form-control" value="${this.escapeHtml(edu.dates_left)}" 
                               placeholder="e.g., Sep 2020 - May 2024"
                               onchange="window.resumeEditor.updateEducation(${index}, 'dates_left', this.value)">
                    </div>
                    <div class="form-group">
                        <label>Location</label>
                        <input type="text" class="form-control" value="${this.escapeHtml(edu.location_right)}" 
                               placeholder="City, Country"
                               onchange="window.resumeEditor.updateEducation(${index}, 'location_right', this.value)">
                    </div>
                </div>
            </div>
        `).join('');
    }

    updateEducation(index, field, value) {
        if (this.resumeData.education[index]) {
            this.resumeData.education[index][field] = value;
            this.updatePreview();
        }
    }

    // Experience management
    addExperience() {
        const experience = {
            title_bold_left: '',
            date_right_nowrap: '',
            bullets: []
        };
        
        this.resumeData.experience.push(experience);
        this.renderExperienceList();
        this.updatePreview();
    }

    removeExperience(index) {
        this.resumeData.experience.splice(index, 1);
        this.renderExperienceList();
        this.updatePreview();
    }

    renderExperienceList() {
        const container = document.querySelector('#experience-list');
        if (!container) return;

        container.innerHTML = this.resumeData.experience.map((exp, index) => this.renderEntry(exp, index, 'experience', 'Experience')).join('');
    }

    updateExperience(index, field, value) {
        if (this.resumeData.experience[index]) {
            this.resumeData.experience[index][field] = value;
            this.updatePreview();
        }
    }

    // Projects management
    addProject() {
        const project = {
            title_bold_left: '',
            date_right_nowrap: '',
            bullets: []
        };
        
        this.resumeData.projects.push(project);
        this.renderProjectsList();
        this.updatePreview();
    }

    removeProject(index) {
        this.resumeData.projects.splice(index, 1);
        this.renderProjectsList();
        this.updatePreview();
    }

    renderProjectsList() {
        const container = document.querySelector('#projects-list');
        if (!container) return;

        container.innerHTML = this.resumeData.projects.map((proj, index) => this.renderEntry(proj, index, 'projects', 'Project')).join('');
    }

    updateProject(index, field, value) {
        if (this.resumeData.projects[index]) {
            this.resumeData.projects[index][field] = value;
            this.updatePreview();
        }
    }

    // Generic entry renderer for experience/projects
    renderEntry(entry, index, type, label) {
        const bullets = Array.isArray(entry.bullets) ? entry.bullets : [];
        
        return `
            <div class="entry-item">
                <div class="entry-header">
                    <h4>${label} ${index + 1}</h4>
                    <div class="entry-controls">
                        <button type="button" class="btn btn-danger btn-sm" onclick="window.resumeEditor.remove${type.charAt(0).toUpperCase() + type.slice(1, -1)}(${index})">Remove</button>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Title</label>
                        <input type="text" class="form-control" value="${this.escapeHtml(entry.title_bold_left)}" 
                               onchange="window.resumeEditor.update${type.charAt(0).toUpperCase() + type.slice(1, -1)}(${index}, 'title_bold_left', this.value)">
                    </div>
                    <div class="form-group">
                        <label>Date (right-aligned)</label>
                        <input type="text" class="form-control" value="${this.escapeHtml(entry.date_right_nowrap)}" 
                               placeholder="e.g., Jan 2023 - Present"
                               onchange="window.resumeEditor.update${type.charAt(0).toUpperCase() + type.slice(1, -1)}(${index}, 'date_right_nowrap', this.value)">
                    </div>
                </div>
                <div class="entry-bullets">
                    <label>Bullets</label>
                    <div class="bullets-list">
                        ${bullets.map((bullet, bulletIndex) => `
                            <div class="bullet-item">
                                <input type="text" class="form-control" value="${this.escapeHtml(bullet)}" 
                                       onchange="window.resumeEditor.updateBullet('${type}', ${index}, ${bulletIndex}, this.value)">
                                <button type="button" class="bullet-remove" onclick="window.resumeEditor.removeBullet('${type}', ${index}, ${bulletIndex})">×</button>
                            </div>
                        `).join('')}
                    </div>
                    <button type="button" class="btn btn-outline btn-sm" onclick="window.resumeEditor.addBullet('${type}', ${index})">+ Add Bullet</button>
                </div>
            </div>
        `;
    }

    // Bullet management
    addBullet(type, entryIndex) {
        const entry = this.resumeData[type][entryIndex];
        if (!entry) return;

        if (!Array.isArray(entry.bullets)) {
            entry.bullets = [];
        }

        entry.bullets.push('');
        
        if (type === 'experience') {
            this.renderExperienceList();
        } else if (type === 'projects') {
            this.renderProjectsList();
        } else if (type === 'custom_sections') {
            this.renderCustomSectionsList();
        }
        
        this.updatePreview();
    }

    removeBullet(type, entryIndex, bulletIndex) {
        const entry = this.resumeData[type][entryIndex];
        if (!entry || !Array.isArray(entry.bullets)) return;

        entry.bullets.splice(bulletIndex, 1);
        
        if (type === 'experience') {
            this.renderExperienceList();
        } else if (type === 'projects') {
            this.renderProjectsList();
        } else if (type === 'custom_sections') {
            this.renderCustomSectionsList();
        }
        
        this.updatePreview();
    }

    updateBullet(type, entryIndex, bulletIndex, value) {
        const entry = this.resumeData[type][entryIndex];
        if (!entry || !Array.isArray(entry.bullets)) return;

        entry.bullets[bulletIndex] = value;
        this.updatePreview();
    }

    // Custom sections management
    addCustomSection() {
        const section = {
            heading: '',
            bullets: []
        };
        
        this.resumeData.custom_sections.push(section);
        this.renderCustomSectionsList();
        this.updatePreview();
    }

    removeCustomSection(index) {
        this.resumeData.custom_sections.splice(index, 1);
        this.renderCustomSectionsList();
        this.updatePreview();
    }

    renderCustomSectionsList() {
        const container = document.querySelector('#custom-sections-list');
        if (!container) return;

        container.innerHTML = this.resumeData.custom_sections.map((section, index) => {
            const bullets = Array.isArray(section.bullets) ? section.bullets : [];
            
            return `
                <div class="entry-item">
                    <div class="entry-header">
                        <h4>Custom Section ${index + 1}</h4>
                        <div class="entry-controls">
                            <button type="button" class="btn btn-danger btn-sm" onclick="window.resumeEditor.removeCustomSection(${index})">Remove</button>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Section Title</label>
                        <input type="text" class="form-control" value="${this.escapeHtml(section.heading)}" 
                               placeholder="e.g., Certifications, Languages, Volunteer Work"
                               onchange="window.resumeEditor.updateCustomSection(${index}, 'heading', this.value)">
                    </div>
                    <div class="entry-bullets">
                        <label>Content</label>
                        <div class="bullets-list">
                            ${bullets.map((bullet, bulletIndex) => `
                                <div class="bullet-item">
                                    <input type="text" class="form-control" value="${this.escapeHtml(bullet)}" 
                                           onchange="window.resumeEditor.updateBullet('custom_sections', ${index}, ${bulletIndex}, this.value)">
                                    <button type="button" class="bullet-remove" onclick="window.resumeEditor.removeBullet('custom_sections', ${index}, ${bulletIndex})">×</button>
                                </div>
                            `).join('')}
                        </div>
                        <button type="button" class="btn btn-outline btn-sm" onclick="window.resumeEditor.addBullet('custom_sections', ${index})">+ Add Item</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    updateCustomSection(index, field, value) {
        if (this.resumeData.custom_sections[index]) {
            this.resumeData.custom_sections[index][field] = value;
            this.updatePreview();
        }
    }

    // Utility functions
    setNestedValue(obj, path, value) {
        const keys = path.split('.');
        let current = obj;
        
        for (let i = 0; i < keys.length - 1; i++) {
            if (!(keys[i] in current)) {
                current[keys[i]] = {};
            }
            current = current[keys[i]];
        }
        
        current[keys[keys.length - 1]] = value;
    }

    escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updatePreview() {
        if (this.preview) {
            this.preview.updateResume(this.resumeData);
        }
    }

    loadResumeData(data) {
        this.resumeData = this.initializeResumeData(data);
        
        // Update form fields
        this.updateFormFields();
        
        // Render dynamic entries
        this.renderExperienceEntries();
        this.renderProjectEntries();
        
        // Update preview
        this.updatePreview();
    }

    updateFormFields() {
        // Update all form fields with current data
        const fields = {
            '#name': 'name',
            '#role': 'role', 
            '#email': 'email',
            '#phone': 'phone',
            '#location': 'location',
            '#github': 'github',
            '#website': 'website',
            '#summary': 'summary',
            '#skills_programming': 'skills.programming',
            '#skills_database': 'skills.database', 
            '#skills_aiml': 'skills.aiml',
            '#skills_tools': 'skills.tools',
            '#skills_soft': 'skills.soft',
            '#skills_additional': 'skills.additional',
            '#edu_degree': 'education.degree',
            '#edu_institution': 'education.institution',
            '#edu_dates': 'education.dates',
            '#edu_loc': 'education.loc'
        };
        
        Object.entries(fields).forEach(([selector, path]) => {
            const element = document.querySelector(selector);
            if (element) {
                const value = this.getNestedValue(this.resumeData, path);
                element.value = value || '';
            }
        });
    }

    getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => current && current[key], obj);
    }

    // Public API
    getResumeData() {
        return this.resumeData;
    }

    exportHTML() {
        return this.preview ? this.preview.exportHTML() : '';
    }
}

// Global functions for template button compatibility
window.addExp = function() { 
    if (window.resumeEditor) {
        window.resumeEditor.addExp();
    }
};

window.addProj = function() { 
    if (window.resumeEditor) {
        window.resumeEditor.addProj();
    }
};

window.editField = function(bucket, i, field, val) { 
    if (window.resumeEditor) {
        if (bucket === 'experience') {
            window.resumeEditor.updateExperienceField(i, field, val);
        } else if (bucket === 'projects') {
            window.resumeEditor.updateProjectField(i, field, val);
        }
    }
};

window.removeEntry = function(bucket, idx) { 
    if (window.resumeEditor) {
        if (bucket === 'experience') {
            window.resumeEditor.removeExperienceEntry(idx);
        } else if (bucket === 'projects') {
            window.resumeEditor.removeProjectEntry(idx);
        }
    }
};