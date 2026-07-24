# Django Resume Maker - Features Checklist

---
## Deferred: outbound email (paused 2026-07-24)

Password reset by email does not work in production and is **parked on purpose**.
The supported way to change a password is the signed-in form at `/your-profile/`,
which needs no email at all.

What is already done:

- `EMAIL_HOST=smtp.resend.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True` and
  `HOST_EMAIL=resend` are set in all Vercel environments.
- Django's stock SMTP backend is already correct for Resend; no code change is needed.

What remains, when it is worth doing:

1. Create a free Resend account (3,000 emails/month, 100/day — far more than
   resets need). The Vercel Marketplace listing is **not** the path: it has no
   free tier, only Pro at $20/month.
2. Add and verify `hillmanchan.com` in Resend, then set
   `DEFAULT_FROM_EMAIL='AceInterview <noreply@hillmanchan.com>'`.
3. Set `HOST_PASSWORD` to the Resend API key and redeploy.
4. Send a real reset against production and confirm delivery — a 302 from
   `/password-reset/` only means the view returned, not that mail left.

Until step 3, the "Forgot password?" link on the login page leads nowhere useful.
Consider hiding it rather than letting it silently fail for real users.

---
## Pages
- [X] Home page
- [X] Login 
- [X] Register 
- [X] Reset password 
- [X] Job Analysis 
- [X] Job Analysis finish 
- [X] Resume Analysis 
- [X] Resume Analysis finish 
- [ ] Build Resume 
- [ ] Resume Finalize  
- [ ] Coding Assessment
    - [ ] Set up different interview links
        - [ ] video interviews
        - [ ] coding assessment 
        - [ ] (upcoming)
- [ ] Customer support 
    - [ ] Articles page ( add later )
- [ ] My dashboard 
    - [ ] Setting  
    - [ ] personal details
    - [ ] (add later)
- [ ] footer 
    - [ ] About us
    - [ ] Contact
    - [ ] Terms of Service
    - [ ] Privacy Policy
    - [ ] Cookie Policy 
    

## Home Page
- [X] Display project title and brief description
- [X] Navigation to login, register, and other main sections
- [X] Footer with basic links (About, Contact)

## Login 
- [X] Form for username and password
- [X] Login button
- [X] Link to password reset and registration page
- [ ] Error messages for incorrect login details

## Register 
- [ ] Form fields for username, email, password
- [ ] Validation for form inputs
- [ ] Register button
- [ ] Redirect to login upon successful registration

## Job Analysis 
- [ ] Form fields for job details
- [ ] Submit button to analyze job details
- [ ] Button to proceed to job analysis results

## Job analysis finish
- [ ] Display job analysis summary
- [ ] Recommended next steps button 
- [ ] Option to go back and analyze next job 

## Resume Analysis 
- [ ] Form for uploading resume file and job details
- [ ] Upload button 
- [ ] Status message or loading image while analyzing 
- [ ] Link to analysis results

## Resume Analysis Finish
- [ ] Display analysis summary 
- [ ] Suggested improvements 
- [ ] Button to proceed to build resume
- [ ] Button to analysis another job or another resume
- [ ] Future for one time analysis everyday limit to free plan 

## Build Resume 
- [ ] Section to add personal details
- [ ] Form fields for each section
- [ ] Real-time preview alongside form
- [ ] Save editing progress for next time
- [ ] Drag-and-drop functionality to record sections
- [ ] Option to choose templates
- [ ] Link to Resume Finalize

## Resume Finalize
- [ ] Final preview for resume
- [ ] Export options (PDF/DOCX)
- [ ] Save resume button
- [ ] Confirmation message upon successful export/save 

## Customer Support 
- [ ] FAQ section with expandable questions 
- [ ] Contact form for support inquiries
- [ ] Links to popular articles (add article later)
- [ ] Customer support chatbox

## My Dashboard
- [ ] Overview of user activities and progress
- [ ] Personal information
    - [ ] Profile picture upload
    - [ ] Link to personal details
    - [ ] update account details
- [ ] Setting page
    - [ ] Theme
    - [ ] Language
    
- [ ] My current plan 
- [ ] log out button




## Footer
- [ ] About Us section link
- [ ] Contact Us section link
- [ ] Links to Terms of Service, Privacy policy, Cookie Policy
- [ ] Social medial icons
