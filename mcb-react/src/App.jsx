import React, { useEffect } from 'react';
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
  const { resetState } = useMCB();

  // Logo click to reset functionality (was missing!)
  const handleLogoClick = () => {
    resetState();
    window.scrollTo({ top: 0, behavior: 'smooth' });
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
        <div className="logo" onClick={handleLogoClick}>
          {/* Updated logo with uploaded file */}
          <img 
            src="/logo.png" 
            alt="MCB – Most Common Blunder" 
            height={80}
            onError={(e) => {
              e.target.style.display = 'none';
              console.warn('Logo image not found');
            }}
          />
          <div className="logo-text">
            <span className="mcb-title">MCB</span>
            <p>Most Common Blunder Analysis</p>
          </div>
        </div>
      </header>

      <main className="main-content">
        {/* Analysis Form */}
        <AnalysisForm />
        
        {/* Progress Section */}
        <ProgressBar />
        
        {/* Results Section */}
        <ResultsSection />
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
