import React from 'react';

/**
 * Top-level React ErrorBoundary component.
 * Catches any render errors in child components and displays a helpful UI
 * with an error trace and a "Reset App State" button, preventing silent blank screens.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an unhandled error during render:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    try {
      localStorage.removeItem('tutor_session_id');
      localStorage.removeItem('tutor_auto_speak');
    } catch {
      // Safe ignore storage access errors
    }
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          background: '#0F172A',
          color: '#F8FAFC',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          <div style={{
            maxWidth: '640px',
            width: '100%',
            background: '#1E293B',
            borderRadius: '16px',
            padding: '32px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            border: '1px solid #334155',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>⚠️</div>
            <h2 style={{ fontSize: '22px', fontWeight: 700, marginBottom: '12px', color: '#F1F5F9' }}>
              Something went wrong
            </h2>
            <p style={{ fontSize: '14px', color: '#94A3B8', marginBottom: '20px', lineHeight: 1.5 }}>
              The application encountered a runtime error while rendering.
            </p>
            {this.state.error && (
              <pre style={{
                textAlign: 'left',
                background: '#090D16',
                color: '#EF4444',
                padding: '16px',
                borderRadius: '8px',
                fontSize: '12px',
                overflowX: 'auto',
                marginBottom: '24px',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: '220px'
              }}>
                {this.state.error.toString()}
                {this.state.errorInfo?.componentStack}
              </pre>
            )}
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button
                type="button"
                onClick={this.handleReset}
                style={{
                  background: '#2563EB',
                  color: '#FFFFFF',
                  border: 'none',
                  padding: '12px 24px',
                  borderRadius: '8px',
                  fontWeight: 600,
                  fontSize: '14px',
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                onMouseOver={(e) => (e.target.style.background = '#1D4ED8')}
                onMouseOut={(e) => (e.target.style.background = '#2563EB')}
              >
                Reset App State
              </button>
              <button
                type="button"
                onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
                style={{
                  background: 'transparent',
                  color: '#94A3B8',
                  border: '1px solid #475569',
                  padding: '12px 20px',
                  borderRadius: '8px',
                  fontWeight: 500,
                  fontSize: '14px',
                  cursor: 'pointer',
                }}
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
