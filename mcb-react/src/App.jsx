import React, { useEffect, useRef } from 'react';
// Stagewise toolbar (AI-powered UI editing)
// Only loaded in development builds – the package handles conditional rendering internally
import { StagewiseToolbar } from '@stagewise/toolbar-react';
import ReactPlugin from '@stagewise-plugins/react';
import { MCBProvider, useMCB } from './context/MCBContext';
import AnalysisForm from './components/forms/AnalysisForm';
import ProgressBar from './components/ui/ProgressBar';
import ResultsSection from './components/results/ResultsSection';
import './styles/main.css';

// Inner App component that has access to MCB context
const AppContent = () => {
  const { ui, analysis, resetState } = useMCB();
  const progressRef = useRef(null);
  const resultsRef = useRef(null);

  useEffect(() => {
    if (analysis.sessionId && ui.progressVisible && progressRef.current) {
      setTimeout(() => {
        progressRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100); // Small delay to ensure the element is rendered
    }
  }, [analysis.sessionId]); // Re-trigger scroll on every new analysis

  useEffect(() => {
    if (ui.resultsVisible && resultsRef.current) {
      setTimeout(() => {
        const yOffset = -80; // Negative offset to add padding on top
        const y = resultsRef.current.getBoundingClientRect().top + window.pageYOffset + yOffset;
        window.scrollTo({ top: y, behavior: 'smooth' });
      }, 100); // Small delay for rendering
    }
  }, [ui.resultsVisible]);

  // Logo click to reset functionality (was missing!)
  const handleLogoClick = () => {
    if (window.confirm("Do you want to start a new analysis? This will clear the current session.")) {
      resetState();
    }
  };

  // Global error handling (was missing!)
  useEffect(() => {
    const handleError = (event) => {
      console.error('Global error:', event.error);
    };

    const handleUnhandledRejection = (event) => {
      console.error('Unhandled promise rejection:', event.reason);
    };

    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    // Console startup messages (was missing!)
    console.log('🎯 MCB Application Starting (React)');
    console.log('✅ MCB Application Ready');

    return () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

  return (
    <div className="container">
      <header className="header">
        <div className="header-container">
          <div className="logo-section" onClick={handleLogoClick}>
            <img 
              src="/logo.png" 
              alt="MCB Logo" 
              className="logo-image"
              onError={(e) => {
                e.target.style.display = 'none';
                console.warn('Logo image not found');
              }}
            />
            <div className="title-section">
              <h1 className="mcb-title">MCB</h1>
              <span className="tagline">Most Common Blunder Analysis</span>
            </div>
          </div>
        </div>
      </header>

      <main className="main-content">
        {/* Analysis Form */}
        <AnalysisForm />
        
        {/* Progress Section */}
        <div ref={progressRef}>
          {ui.progressVisible && <ProgressBar />}
        </div>
        
        <div ref={resultsRef}>
          {ui.resultsVisible && <ResultsSection />}
        </div>
      </main>

      <footer className="footer">
        <p>&copy; 2025 MCB Project</p>
      </footer>

      {/* Stagewise AI toolbar – visible only in dev */}
      {import.meta.env.DEV && (
        <StagewiseToolbar config={{ plugins: [ReactPlugin] }} />
      )}
    </div>
  );
};

function App() {
  return (
    <MCBProvider>
      <AppContent />
    </MCBProvider>
  );
}

export default App;
