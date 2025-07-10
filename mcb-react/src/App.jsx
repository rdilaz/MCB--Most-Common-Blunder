import React, { useEffect } from 'react';
import { MCBProvider, useMCB } from './context/MCBContext';
import AnalysisForm from './components/forms/AnalysisForm';
import ProgressBar from './components/ui/ProgressBar';
import ResultsSection from './components/results/ResultsSection';
import './styles/main.css';

// TODO: Add stagewise integration when packages are available
// const StagewiseToolbar = import.meta.env.DEV 
//   ? React.lazy(() => import('@stagewise/toolbar-react').then(module => ({ default: module.StagewiseToolbar })))
//   : null;

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
          <h1>🎯 MCB</h1>
          <p>Most Common Blunder Analysis</p>
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
