import React from 'react';
import { MCBProvider } from './context/MCBContext';
import AnalysisForm from './components/forms/AnalysisForm';
import ProgressBar from './components/ui/ProgressBar';
import ResultsSection from './components/results/ResultsSection';
import './styles/main.css';

// TODO: Add stagewise integration when packages are available
// const StagewiseToolbar = import.meta.env.DEV 
//   ? React.lazy(() => import('@stagewise/toolbar-react').then(module => ({ default: module.StagewiseToolbar })))
//   : null;

function App() {
  return (
    <MCBProvider>
      <div className="container">
        <header className="header">
          <div className="logo">
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
    </MCBProvider>
  );
}

export default App;
