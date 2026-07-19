/**
 * AI Resume A4 Preview with Zoom Controls
 * Renders EditableResume data using exact styling from live_preview_template.html
 */

class AIResumePreview {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentZoom = 100;
        this.resumeData = null;
        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="ai-resume-preview">
                <div class="ai-resume-zoom-controls">
                    <button data-zoom="75">75%</button>
                    <button data-zoom="100" class="active">100%</button>
                    <button data-zoom="125">125%</button>
                    <button data-zoom="150">150%</button>
                </div>
                <div class="ai-resume-sheet zoom-100" id="ai-resume-content">
                    <!-- Resume pages will be rendered here -->
                </div>
            </div>
        `;

        this.previewElement = this.container.querySelector('.ai-resume-preview');
        this.sheetElement = this.container.querySelector('.ai-resume-sheet');
        this.contentElement = this.container.querySelector('#ai-resume-content');
        
        this.setupZoomControls();
    }

    setupZoomControls() {
        const buttons = this.container.querySelectorAll('.ai-resume-zoom-controls button');
        
        buttons.forEach(button => {
            button.addEventListener('click', () => {
                const zoom = parseInt(button.dataset.zoom);
                this.setZoom(zoom);
                
                // Update active button
                buttons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
            });
        });
    }

    setZoom(zoom) {
        this.currentZoom = zoom;
        
        // Remove all zoom classes
        this.sheetElement.classList.remove('zoom-75', 'zoom-100', 'zoom-125', 'zoom-150');
        
        // Add current zoom class
        this.sheetElement.classList.add(`zoom-${zoom}`);
    }

    render(resumeData) {
        this.resumeData = resumeData;
        
        if (!resumeData) {
            this.renderEmptyState();
            return;
        }

        const resumeHTML = this.buildResumeHTML(resumeData);
        
        // Display resume directly as single page (like live template)
        this.contentElement.innerHTML = resumeHTML;
    }

    buildResumeHTML(data) {
        const escapeHtml = (str) => {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        };

        const textOrPlaceholder = (text, placeholder) => {
            if (text && text.trim()) {
                return escapeHtml(text);
            }
            return `<span class="placeholder">${placeholder}</span>`;
        };

        const renderSkillsList = (skills) => {
            const categories = [
                ['Programming', skills.programming],
                ['Database', skills.database], 
                ['AI/ML Tools', skills.aiml],
                ['Tools & Methodologies', skills.tools],
                ['Soft Skills', skills.soft],
                ['Additional', skills.additional]
            ];

            return categories.map(([label, items]) => {
                const skillText = Array.isArray(items) ? items.join(', ') : (items || '');
                return `<li><b>${label}:</b> ${textOrPlaceholder(skillText, '')}</li>`;
            }).join('');
        };

        const renderEducation = (education) => {
            if (!education || typeof education !== 'object') {
                return `
                    <p class="edu-degree">${textOrPlaceholder('', 'Degree')}</p>
                    <p class="edu-institution">${textOrPlaceholder('', 'Institution')}</p>
                    <div class="edu-meta">
                        <div>${textOrPlaceholder('', 'Dates')}</div>
                        <div>${textOrPlaceholder('', 'Location')}</div>
                    </div>
                `;
            }

            return `
                <p class="edu-degree">${textOrPlaceholder(education.degree, 'Degree')}</p>
                <p class="edu-institution">${textOrPlaceholder(education.institution, 'Institution')}</p>
                <div class="edu-meta">
                    <div>${textOrPlaceholder(education.dates, 'Dates')}</div>
                    <div>${textOrPlaceholder(education.loc, 'Location')}</div>
                </div>
            `;
        };

        const renderEntryList = (entries, sectionName) => {
            if (!Array.isArray(entries) || entries.length === 0) {
                return '';
            }

            return entries.map(entry => {
                // Handle both string and array format for bullets
                let bullets = [];
                if (typeof entry.bullets === 'string' && entry.bullets.trim()) {
                    bullets = entry.bullets.split(/\r?\n/).map(b => b.trim()).filter(Boolean);
                } else if (Array.isArray(entry.bullets)) {
                    bullets = entry.bullets.filter(Boolean);
                }
                
                const bulletHTML = bullets.length > 0 
                    ? `<ul class="bullet-list">${bullets.map(bullet => `<li>${escapeHtml(bullet)}</li>`).join('')}</ul>`
                    : '';

                return `
                    <div class="entry-header">
                        <p class="entry-title">${textOrPlaceholder(entry.title, `${sectionName} Title`)}</p>
                        <p class="entry-date">${textOrPlaceholder(entry.date, 'Date')}</p>
                    </div>
                    ${bulletHTML}
                `;
            }).join('');
        };

        const renderCustomSections = (customSections) => {
            if (!Array.isArray(customSections) || customSections.length === 0) {
                return '';
            }

            return customSections.map(section => {
                const bullets = Array.isArray(section.bullets) ? section.bullets : [];
                const bulletHTML = bullets.length > 0
                    ? `<ul class="ai-resume-bullet-list">${bullets.map(bullet => `<li>${escapeHtml(bullet)}</li>`).join('')}</ul>`
                    : '';

                return `
                    <section class="ai-resume-custom-section">
                        <h2 class="ai-resume-custom-section-title">${escapeHtml(section.heading || 'Custom Section')}</h2>
                        ${bulletHTML}
                    </section>
                `;
            }).join('');
        };

        // Build complete resume HTML - single page format like live template
        return `
            <div class="page">
                <h1 class="name">${textOrPlaceholder(data.name, 'Your Full Name')}</h1>
                <p class="role">${textOrPlaceholder(data.role, 'Role / Title')}</p>
                
                <div class="contact-row">
                    <div class="left">${textOrPlaceholder(data.email, 'email@example.com')}</div>
                    <div class="center">${textOrPlaceholder(data.phone, '+44 xxxx xxx xxx')}</div>
                    <div class="right">${textOrPlaceholder(data.location, 'City, Country')}</div>
                </div>
                
                <div class="contact-row">
                    <div class="left">GitHub: ${data.github 
                        ? `<a href="${escapeHtml(data.github)}">${escapeHtml(data.github)}</a>`
                        : '<span class="placeholder">https://github.com/username</span>'}</div>
                    <div class="center"></div>
                    <div class="right">Website: ${data.website
                        ? `<a href="${escapeHtml(data.website)}">${escapeHtml(data.website)}</a>`
                        : '<span class="placeholder">yourdomain.com</span>'}</div>
                </div>

                <section class="section">
                    <h2 class="section-title">SUMMARY</h2>
                    <p class="summary">${textOrPlaceholder(data.summary, 'Short summary paragraph')}</p>
                </section>

                <section class="section">
                    <h2 class="section-title">SKILLS</h2>
                    <ul class="skills-list">
                        ${renderSkillsList(data.skills || {})}
                    </ul>
                </section>

                <section class="section">
                    <h2 class="section-title">EDUCATION</h2>
                    ${renderEducation(data.education)}
                </section>

                <section class="section">
                    <h2 class="section-title">EXPERIENCE</h2>
                    ${renderEntryList(data.experience, 'Experience')}
                </section>

                <section class="section">
                    <h2 class="section-title">PROJECTS</h2>
                    ${renderEntryList(data.projects, 'Project')}
                </section>

                ${renderCustomSections(data.custom_sections)}
            </div>
        `;
    }

    // Pagination logic - exact from live_preview_template.html
    paginate(sourceElement) {
        const PAGE_H_PX = this.measurePt(841.89);
        
        // Create temp page to read paddings
        const tempPage = document.createElement('div');
        tempPage.className = 'page';
        tempPage.style.visibility = 'hidden';
        this.contentElement.appendChild(tempPage);
        
        const cs = getComputedStyle(tempPage);
        const padTop = parseFloat(cs.paddingTop) || 0;
        const padBottom = parseFloat(cs.paddingBottom) || 0;
        const innerH = PAGE_H_PX - padTop - padBottom;
        
        this.contentElement.removeChild(tempPage);
        const reserve = this.measurePt(10);

        // Collect nodes to place
        const nodes = Array.from(sourceElement.childNodes).filter(n => (
            n.nodeType === Node.ELEMENT_NODE || 
            (n.nodeType === Node.TEXT_NODE && n.textContent.trim().length)
        ));

        let page, inner;
        const newPage = () => {
            page = document.createElement('div');
            page.className = 'page';
            this.contentElement.appendChild(page);
            inner = page; // No need for inner wrapper, just use page directly
        };

        newPage();

        for (const node of nodes) {
            const el = (node.nodeType === Node.TEXT_NODE) 
                ? (() => { const w = document.createElement('div'); w.textContent = node.textContent; return w; })()
                : node;
            
            // Try to add element to current page
            inner.appendChild(el);
            
            // Force layout
            void inner.offsetHeight;
            
            // Check if page is overflowing
            if (inner.scrollHeight > (innerH - reserve)) {
                // Remove the element that caused overflow
                inner.removeChild(el);
                
                // Only create new page if current page has content
                if (inner.children.length > 0) {
                    newPage();
                }
                
                // Add element to new page
                inner.appendChild(el);
                void inner.offsetHeight;
            }
        }
    }

    measurePt(pt) {
        const probe = document.createElement('div');
        probe.style.position = 'absolute';
        probe.style.visibility = 'hidden';
        probe.style.height = pt + 'pt';
        document.body.appendChild(probe);
        const h = probe.getBoundingClientRect().height;
        probe.remove();
        return h;
    }

    renderEmptyState() {
        this.contentElement.innerHTML = `
            <div class="page">
                <h1 class="name">
                    <span class="placeholder">Your Full Name</span>
                </h1>
                <p class="role">
                    <span class="placeholder">Role / Title</span>
                </p>
                <div class="contact-row">
                    <div class="left"><span class="placeholder">email@example.com</span></div>
                    <div class="center"><span class="placeholder">+44 xxxx xxx xxx</span></div>
                    <div class="right"><span class="placeholder">City, Country</span></div>
                </div>
                <div class="contact-row">
                    <div class="left">GitHub: <span class="placeholder">https://github.com/username</span></div>
                    <div class="center"></div>
                    <div class="right">Website: <span class="placeholder">yourdomain.com</span></div>
                </div>
                <section class="section">
                    <h2 class="section-title">SUMMARY</h2>
                    <p class="summary"><span class="placeholder">Short summary paragraph</span></p>
                </section>
            </div>
        `;
    }

    // Public API
    updateResume(resumeData) {
        this.render(resumeData);
    }

    getZoom() {
        return this.currentZoom;
    }

    exportHTML() {
        // Return HTML suitable for PDF generation
        if (!this.resumeData) return '';
        
        return `
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Resume</title>
                <style>
                    @page { size: A4; margin: 0; }
                    body { margin: 0; padding: 0; }
                    ${this.getExportCSS()}
                </style>
            </head>
            <body>
                ${this.buildResumeHTML(this.resumeData)}
            </body>
            </html>
        `;
    }

    getExportCSS() {
        // Return CSS optimized for PDF export
        return `
            .ai-resume-page {
                box-sizing: border-box;
                width: 595.28pt;
                height: 841.89pt;
                padding: 28.2pt 15.5pt 32pt 21.5pt;
                background: #fff;
                page-break-after: always;
            }
            
            .ai-resume-name {
                font-family: "Times New Roman", Times, serif;
                font-weight: 700;
                font-size: 32pt;
                line-height: 1.05;
                text-align: center;
                margin: 0;
                color: #000;
            }
            
            .ai-resume-role {
                font-family: "Times New Roman", Times, serif;
                font-weight: 700;
                font-size: 19.5pt;
                text-align: center;
                margin: 0.6em 0 0;
                color: #000;
            }
            
            .ai-resume-contact-row {
                display: grid;
                grid-template-columns: 1fr auto 1fr;
                align-items: baseline;
                column-gap: 12pt;
                margin-top: 0.8em;
            }
            
            .ai-resume-contact-row .left,
            .ai-resume-contact-row .center,
            .ai-resume-contact-row .right {
                font-family: "Times New Roman", Times, serif;
                font-size: 11pt;
                line-height: 1.2;
                white-space: nowrap;
                min-width: 0;
                color: #000;
            }
            
            .ai-resume-contact-row .left { justify-self: start; }
            .ai-resume-contact-row .center { justify-self: center; }
            .ai-resume-contact-row .right { justify-self: end; text-align: right; }
            .ai-resume-contact-row a { color: #000; text-decoration: none; }
            
            .ai-resume-section { margin-top: 1.35em; }
            .ai-resume-section-title {
                font-family: "Times New Roman", Times, serif;
                font-weight: 700;
                font-size: 14pt;
                text-transform: uppercase;
                margin: 0;
                padding-bottom: 6pt;
                border-bottom: 1px solid #000;
                color: #000;
            }
            
            .ai-resume-summary {
                margin-top: 8pt;
                font-family: "Times New Roman", Times, serif;
                font-size: 14pt;
                line-height: 1.14;
                color: #000;
            }
            
            .ai-resume-skills-list { list-style: none; margin: 8pt 0 0; padding: 0; }
            .ai-resume-skills-list li {
                font-family: "Times New Roman", Times, serif;
                font-size: 11pt;
                line-height: 1.2;
                color: #000;
            }
            .ai-resume-skills-list b { font-weight: 700; }
            
            .ai-resume-edu-degree, .ai-resume-edu-institution {
                font-family: "Times New Roman", Times, serif;
                font-weight: 700;
                font-size: 14pt;
                margin: 0.6em 0 0;
                color: #000;
            }
            
            .ai-resume-edu-meta {
                display: flex;
                justify-content: space-between;
                font-family: "Times New Roman", Times, serif;
                font-size: 11pt;
                color: #000;
            }
            
            .ai-resume-entry-header {
                display: flex;
                justify-content: space-between;
                gap: 12pt;
                margin-top: 0.65em;
                align-items: flex-start;
            }
            
            .ai-resume-entry-title {
                font-family: "Times New Roman", Times, serif;
                font-weight: 700;
                font-size: 14pt;
                flex: 1 1 auto;
                min-width: 0;
                margin: 0;
                color: #000;
            }
            
            .ai-resume-entry-date {
                font-family: "Times New Roman", Times, serif;
                font-size: 11pt;
                white-space: nowrap;
                flex: 0 0 auto;
                margin: 0;
                color: #000;
            }
            
            .ai-resume-bullet-list { list-style: none; margin: 6pt 0 0; padding: 0; }
            .ai-resume-bullet-list li {
                position: relative;
                font-family: "Times New Roman", Times, serif;
                font-size: 12pt;
                line-height: 1.22;
                margin: 0.25em 0 0;
                padding-left: 52.5pt;
                color: #000;
            }
            .ai-resume-bullet-list li::before {
                content: "•";
                position: absolute;
                left: 38.52pt;
                top: 0;
                font-size: 12pt;
            }
            
            .ai-resume-custom-section { margin-top: 1.35em; }
            .ai-resume-custom-section-title {
                font-family: "Times New Roman", Times, serif;
                font-weight: 700;
                font-size: 14pt;
                text-transform: uppercase;
                margin: 0;
                padding-bottom: 6pt;
                border-bottom: 1px solid #000;
                color: #000;
            }
            
            .ai-resume-placeholder { display: none; }
        `;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AIResumePreview;
} else if (typeof window !== 'undefined') {
    window.AIResumePreview = AIResumePreview;
}