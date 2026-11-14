import React from 'react';

export const GNANI_LOCALES = [
  { code: 'indic-auto', label: 'Auto-detect', native: 'Indic Auto' },
  { code: 'hi-IN', label: 'Hindi', native: 'हिंदी' },
  { code: 'en-IN', label: 'Indian English', native: 'English' },
  { code: 'ta-IN', label: 'Tamil', native: 'தமிழ்' },
  { code: 'te-IN', label: 'Telugu', native: 'తెలుగు' },
  { code: 'kn-IN', label: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'ml-IN', label: 'Malayalam', native: 'മലയാളം' },
  { code: 'mr-IN', label: 'Marathi', native: 'मराठी' },
  { code: 'pa-IN', label: 'Punjabi', native: 'ਪੰਜਾਬੀ' },
  { code: 'bn-IN', label: 'Bengali', native: 'বাংলা' },
  { code: 'gu-IN', label: 'Gujarati', native: 'ગુજરાતી' },
];

export default function LanguageSelector({ selectedLanguage = 'indic-auto', onLanguageChange }) {
  return (
    <div className="lang-selector-wrapper">
      <label htmlFor="language-select" className="lang-label">
        <svg className="lang-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="2" y1="12" x2="22" y2="12" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
        <span className="sr-only">Language</span>
      </label>
      <select
        id="language-select"
        className="lang-select"
        value={selectedLanguage}
        onChange={(e) => onLanguageChange?.(e.target.value)}
        aria-label="Select tutoring language"
      >
        {GNANI_LOCALES.map((loc) => (
          <option key={loc.code} value={loc.code}>
            {loc.label} ({loc.native})
          </option>
        ))}
      </select>
    </div>
  );
}

