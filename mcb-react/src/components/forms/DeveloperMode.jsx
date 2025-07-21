import React, { useState } from 'react';
import { useMCB } from '../../context/MCBContext';
import { useAnalysis } from '../../hooks/useAnalysis';

const DeveloperMode = () => {
  const { settings, updateSettings } = useMCB();
  const { isAnalyzing, startAnalysis } = useAnalysis();
  const [isExpanded, setIsExpanded] = useState(false);
  const [pgnInput, setPgnInput] = useState('');
  const [isDeveloperMode, setIsDeveloperMode] = useState(false);

  const handlePgnSubmit = async (e) => {
    e.preventDefault();
    
    if (!pgnInput.trim()) {
      alert('Please enter a PGN');
      return;
    }

    try {
      // Create a temporary file with the PGN content
      const formData = new FormData();
      const pgnBlob = new Blob([pgnInput], { type: 'text/plain' });
      formData.append('pgn_file', pgnBlob, 'temp_game.pgn');
      formData.append('username', settings.username || 'developer');
      formData.append('blunder_threshold', settings.blunderThreshold);
      formData.append('engine_think_time', getThinkTime(settings.analysisDepth));
      formData.append('debug', 'true');

      // Send to backend for analysis
      const response = await fetch('/api/analyze-pgn', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      // Display results in a simple alert for now
      if (result.blunders && result.blunders.length > 0) {
        const blunderText = result.blunders.map(blunder => 
          `Move ${blunder.move_number}: ${blunder.category} - ${blunder.description}`
        ).join('\n');
        alert(`Found ${result.blunders.length} blunders:\n\n${blunderText}`);
      } else {
        alert('No blunders found in this game.');
      }

    } catch (error) {
      console.error('PGN analysis failed:', error);
      alert(`Analysis failed: ${error.message}`);
    }
  };

  const getThinkTime = (depth) => {
    switch (depth) {
      case 'fast': return 0.08;
      case 'balanced': return 0.15;
      case 'deep': return 0.3;
      default: return 0.15;
    }
  };

  const toggleDeveloperMode = () => {
    setIsDeveloperMode(!isDeveloperMode);
    if (!isDeveloperMode) {
      setIsExpanded(true);
    }
  };

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  // Only show in development mode
  if (!import.meta.env.DEV) {
    return null;
  }

  return (
    <div className="developer-mode">
      <div className="developer-toggle">
        <button
          type="button"
          className={`dev-toggle-btn ${isDeveloperMode ? 'active' : ''}`}
          onClick={toggleDeveloperMode}
        >
          🔧 Developer Mode {isDeveloperMode ? 'ON' : 'OFF'}
        </button>
      </div>

      {isDeveloperMode && (
        <div className={`dev-panel ${isExpanded ? 'expanded' : 'collapsed'}`}>
          <div 
            className="dev-header" 
            onClick={toggleExpanded}
            style={{ cursor: 'pointer' }}
          >
            <h3>🧪 PGN Test Mode</h3>
            <span className="toggle-icon">{isExpanded ? '▲' : '▼'}</span>
          </div>
          
          <div className={`dev-content ${isExpanded ? '' : 'collapsed'}`}>
            <form onSubmit={handlePgnSubmit}>
              <div className="input-group">
                <label htmlFor="pgnInput">Paste PGN Here</label>
                <textarea
                  id="pgnInput"
                  placeholder="Paste your PGN game here..."
                  value={pgnInput}
                  onChange={(e) => setPgnInput(e.target.value)}
                  rows={8}
                  className="pgn-textarea"
                  required
                />
                <small>Paste a single game PGN to test MCB analysis</small>
              </div>

              <div className="dev-settings">
                <div className="setting-group">
                  <label htmlFor="devUsername">Test Username</label>
                  <input
                    type="text"
                    id="devUsername"
                    placeholder="Enter username for analysis"
                    value={settings.username}
                    onChange={(e) => updateSettings({ username: e.target.value })}
                  />
                </div>

                <div className="setting-group">
                  <label htmlFor="devThreshold">
                    Blunder Threshold: <span>{settings.blunderThreshold}%</span>
                  </label>
                  <input
                    type="range"
                    id="devThreshold"
                    min={5}
                    max={40}
                    value={settings.blunderThreshold}
                    onChange={(e) => updateSettings({ blunderThreshold: parseInt(e.target.value) })}
                  />
                </div>

                <div className="setting-group">
                  <label htmlFor="devDepth">Analysis Depth</label>
                  <select
                    id="devDepth"
                    value={settings.analysisDepth}
                    onChange={(e) => updateSettings({ analysisDepth: e.target.value })}
                  >
                    <option value="fast">Fast (0.08s per move)</option>
                    <option value="balanced">Balanced (0.15s per move)</option>
                    <option value="deep">Deep (0.3s per move)</option>
                  </select>
                </div>
              </div>

              <button 
                type="submit" 
                className="dev-analyze-btn"
                disabled={!pgnInput.trim() || isAnalyzing}
              >
                <span className={`btn-text ${isAnalyzing ? 'hidden' : ''}`}>
                  🧪 Test PGN Analysis
                </span>
                <span className={`btn-loader ${isAnalyzing ? '' : 'hidden'}`}>
                  ⏳ Analyzing...
                </span>
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default DeveloperMode; 