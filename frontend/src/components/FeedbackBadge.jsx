import React from 'react';

export default function FeedbackBadge({ status, detail }) {
  if (!status || status === 'not_applicable') {
    return null;
  }

  const configs = {
    correct: {
      className: 'feedback-badge-correct',
      icon: '✓',
      defaultLabel: 'Step Correct',
    },
    incorrect: {
      className: 'feedback-badge-incorrect',
      icon: '✗',
      defaultLabel: 'Check Step',
    },
    uncertain: {
      className: 'feedback-badge-uncertain',
      icon: '?',
      defaultLabel: 'Needs Review',
    },
  };

  const config = configs[status] || configs.uncertain;

  return (
    <div className={`feedback-badge ${config.className}`} role="status">
      <span className="feedback-badge-icon" aria-hidden="true">
        {config.icon}
      </span>
      <span className="feedback-badge-label">
        {detail || config.defaultLabel}
      </span>
    </div>
  );
}

