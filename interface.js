import React, { useState } from 'react';
import { 
  FileText, 
  Briefcase, 
  FileEdit, 
  Settings, 
  MessageSquare,
  ChevronRight,
  Menu,
  X,
  ArrowRight
} from 'lucide-react';

const Website = () => {
  const [activeSection, setActiveSection] = React.useState('home');
  const [isNavOpen, setIsNavOpen] = useState(true);

  const sections = {
    'home': {
      title: 'Home',
      content: (
        <div className="space-y-8">
          <div className="text-center mb-12">
            <h1 className="text-4xl font-bold text-gray-900 mb-4">Welcome to AceInterview</h1>
            <p className="text-xl text-gray-600">Your complete career acceleration platform</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Job Analysis Card */}
            <div className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow">
              <div className="flex items-center mb-4">
                <Briefcase className="h-8 w-8 text-blue-600" />
                <h3 className="text-xl font-semibold ml-3">Job Analysis</h3>
              </div>
              <p className="text-gray-600 mb-4">Get detailed insights into job requirements and market trends to better understand your target position.</p>
              <button 
                onClick={() => setActiveSection('job-analysis')}
                className="flex items-center text-blue-600 hover:text-blue-800"
              >
                Explore <ArrowRight className="ml-2 h-4 w-4" />
              </button>
            </div>

            {/* Resume Analysis Card */}
            <div className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow">
              <div className="flex items-center mb-4">
                <FileText className="h-8 w-8 text-blue-600" />
                <h3 className="text-xl font-semibold ml-3">Resume Analysis</h3>
              </div>
              <p className="text-gray-600 mb-4">Get professional feedback on your resume and learn how to improve its impact.</p>
              <button 
                onClick={() => setActiveSection('resume-analysis')}
                className="flex items-center text-blue-600 hover:text-blue-800"
              >
                Explore <ArrowRight className="ml-2 h-4 w-4" />
              </button>
            </div>

            {/* Build Resume Card */}
            <div className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow">
              <div className="flex items-center mb-4">
                <FileEdit className="h-8 w-8 text-blue-600" />
                <h3 className="text-xl font-semibold ml-3">Build Resume</h3>
              </div>
              <p className="text-gray-600 mb-4">Create a professional resume using our templates and expert guidance.</p>
              <button 
                onClick={() => setActiveSection('build-resume')}
                className="flex items-center text-blue-600 hover:text-blue-800"
              >
                Explore <ArrowRight className="ml-2 h-4 w-4" />
              </button>
            </div>

            {/* Tailor Resume Card */}
            <div className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow">
              <div className="flex items-center mb-4">
                <Settings className="h-8 w-8 text-blue-600" />
                <h3 className="text-xl font-semibold ml-3">Tailor Resume</h3>
              </div>
              <p className="text-gray-600 mb-4">Customize your resume for specific job applications to increase your chances.</p>
              <button 
                onClick={() => setActiveSection('tailor-resume')}
                className="flex items-center text-blue-600 hover:text-blue-800"
              >
                Explore <ArrowRight className="ml-2 h-4 w-4" />
              </button>
            </div>

            {/* Support Card */}
            <div className="bg-white rounded-lg shadow-lg p-6 hover:shadow-xl transition-shadow">
              <div className="flex items-center mb-4">
                <MessageSquare className="h-8 w-8 text-blue-600" />
                <h3 className="text-xl font-semibold ml-3">Customer Support</h3>
              </div>
              <p className="text-gray-600 mb-4">Get help from our expert team whenever you need assistance.</p>
              <button 
                onClick={() => setActiveSection('support')}
                className="flex items-center text-blue-600 hover:text-blue-800"
              >
                Explore <ArrowRight className="ml-2 h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )
    },
    'job-analysis': {
      title: 'Job Analysis',
      content: (
        <div className="space-y-4">
          <h2 className="text-2xl font-bold">Job Analysis</h2>
          <p className="text-gray-600">Upload a job description and get detailed insights:</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-white rounded-lg shadow">
              <h3 className="font-semibold mb-2">Key Requirements</h3>
              <ul className="list-disc pl-4 text-gray-600">
                <li>Required skills and qualifications</li>
                <li>Experience level analysis</li>
                <li>Industry-specific requirements</li>
              </ul>
            </div>
            <div className="p-4 bg-white rounded-lg shadow">
              <h3 className="font-semibold mb-2">Market Insights</h3>
              <ul className="list-disc pl-4 text-gray-600">
                <li>Salary range analysis</li>
                <li>Industry trends</li>
                <li>Company culture insights</li>
              </ul>
            </div>
          </div>
        </div>
      )
    },
    // ... (keep other existing sections the same)
  };

  const toggleNav = () => {
    setIsNavOpen(!isNavOpen);
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Mobile Nav Toggle Button */}
      <button 
        onClick={toggleNav}
        className="fixed top-4 left-4 z-50 md:hidden bg-white p-2 rounded-lg shadow-lg"
      >
        {isNavOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
      </button>

      {/* Sidebar */}
      <div className={`fixed left-0 top-0 h-screen bg-white shadow-lg transition-transform duration-300 transform 
        ${isNavOpen ? 'translate-x-0' : '-translate-x-full'} 
        ${isNavOpen ? 'w-64' : 'w-0'}
        md:translate-x-0 md:w-64 z-40`}
      >
        <div className="p-6">
          <h1 className="text-2xl font-bold text-blue-600">AceInterview</h1>
        </div>
        <nav className="mt-6">
          <div className="space-y-2 px-4">
            <button
              onClick={() => {
                setActiveSection('home');
                if (window.innerWidth < 768) setIsNavOpen(false);
              }}
              className={`w-full flex items-center px-4 py-2 rounded-lg text-left ${
                activeSection === 'home' 
                  ? 'bg-blue-50 text-blue-600' 
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              Home
              <ChevronRight className="ml-auto h-4 w-4" />
            </button>
            {Object.entries(sections).filter(([key]) => key !== 'home').map(([key, section]) => (
              <button
                key={key}
                onClick={() => {
                  setActiveSection(key);
                  if (window.innerWidth < 768) setIsNavOpen(false);
                }}
                className={`w-full flex items-center px-4 py-2 rounded-lg text-left ${
                  activeSection === key 
                    ? 'bg-blue-50 text-blue-600' 
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                {key === 'job-analysis' && <Briefcase className="mr-2 h-5 w-5" />}
                {key === 'resume-analysis' && <FileText className="mr-2 h-5 w-5" />}
                {key === 'build-resume' && <FileEdit className="mr-2 h-5 w-5" />}
                {key === 'tailor-resume' && <Settings className="mr-2 h-5 w-5" />}
                {key === 'support' && <MessageSquare className="mr-2 h-5 w-5" />}
                {section.title}
                <ChevronRight className="ml-auto h-4 w-4" />
              </button>
            ))}
          </div>
        </nav>
      </div>

      {/* Main Content */}
      <div className={`flex-1 transition-margin duration-300
        ${isNavOpen ? 'md:ml-64' : 'md:ml-0'}
        ${isNavOpen ? 'ml-0' : 'ml-0'}`}
      >
        <main className="p-4 md:p-8 mt-16 md:mt-0">
          {sections[activeSection].content}
        </main>

        {/* Footer */}
        <footer className="bg-white shadow-lg mt-8">
          <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              <div>
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">About Us</h3>
                <ul className="mt-4 space-y-2">
                  <li><a href="#" className="text-gray-600 hover:text-blue-600">Company</a></li>
                  <li><a href="#" className="text-gray-600 hover:text-blue-600">Careers</a></li>
                  <li><a href="#" className="text-gray-600 hover:text-blue-600">Blog</a></li>
                </ul>
              </div>
              {/* ... (keep other footer sections the same) */}
            </div>
            <div className="mt-8 border-t border-gray-200 pt-8 text-center">
              <p className="text-gray-400">&copy; 2024 AceInterview. All rights reserved.</p>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default Website;