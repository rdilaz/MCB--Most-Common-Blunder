import React from 'react';
import { useMCB } from '../../context/MCBContext';
import { useAnalysis } from '../../hooks/useAnalysis';

const AnalysisForm = () => {
  const { settings, updateSettings, validateSettings } = useMCB();
  const { isAnalyzing, startAnalysis } = useAnalysis();

  const handleInputChange = (field, value) => {
    updateSettings({ [field]: value });
  };

  const handleGameTypesChange = (e) => {
    const selectedOptions = Array.from(e.target.selectedOptions, option => option.value);
    updateSettings({ gameTypes: selectedOptions });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    startAnalysis();
  };

  const validation = validateSettings();

  return (
    <div className="input-section">
      <h2>🎮 Chess Analysis</h2>
      <p className="subtitle">
        Identify your most common blunders and improve your game
      </p>

      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <label htmlFor="username">Chess.com Username</label>
          <input
            type="text"
            id="username"
            placeholder="Enter your Chess.com username"
            value={settings.username}
            onChange={(e) => handleInputChange('username', e.target.value)}
            required
          />
        </div>

        {/* Analysis Settings Panel */}
        <div className="settings-panel">
          <h3>⚙️ Analysis Settings</h3>
          <div className="settings-grid">
            <div className="setting-group">
              <label htmlFor="gameCount">
                Number of Games: <span>{settings.gameCount}</span>
              </label>
              <input
                type="range"
                id="gameCount"
                min="1"
                max="50"
                value={settings.gameCount}
                onChange={(e) => handleInputChange('gameCount', parseInt(e.target.value))}
                className="slider"
              />
              <small>Analyze your most recent games (max 50)</small>
            </div>

            <div className="setting-group">
              <label htmlFor="gameTypes">Game Types</label>
              <select 
                multiple 
                id="gameTypes" 
                className="multi-select"
                value={settings.gameTypes}
                onChange={handleGameTypesChange}
              >
                <option value="bullet">🔥 Bullet (1-2 min)</option>
                <option value="blitz">⚡ Blitz (3-5 min)</option>
                <option value="rapid">🎯 Rapid (10-15 min)</option>
                <option value="classical">🏰 Classical (30+ min)</option>
              </select>
              <small>Hold Ctrl/Cmd to select multiple</small>
            </div>

            <div className="setting-group">
              <label htmlFor="ratingFilter">Rating Filter</label>
              <select 
                id="ratingFilter"
                value={settings.ratingFilter}
                onChange={(e) => handleInputChange('ratingFilter', e.target.value)}
              >
                <option value="all">All Games</option>
                <option value="rated">Rated Games Only</option>
                <option value="unrated">Unrated Games Only</option>
              </select>
            </div>

            <div className="setting-group">
              <label htmlFor="gameResult">Game Results</label>
              <select 
                id="gameResult"
                value={settings.gameResult}
                onChange={(e) => handleInputChange('gameResult', e.target.value)}
              >
                <option value="all">All Games</option>
                <option value="wins">Wins Only</option>
                <option value="losses">Losses Only</option>
              </select>
              <small>Filter by game outcome</small>
            </div>

            <div className="setting-group">
              <label htmlFor="blunderThreshold">
                Blunder Threshold: <span>{settings.blunderThreshold}</span>%
              </label>
              <input
                type="range"
                id="blunderThreshold"
                min="5"
                max="30"
                value={settings.blunderThreshold}
                onChange={(e) => handleInputChange('blunderThreshold', parseInt(e.target.value))}
                className="slider"
              />
              <small>Win probability drop % to be considered a blunder</small>
            </div>

            <div className="setting-group">
              <label htmlFor="analysisDepth">Analysis Depth</label>
              <select 
                id="analysisDepth"
                value={settings.analysisDepth}
                onChange={(e) => handleInputChange('analysisDepth', e.target.value)}
              >
                <option value="fast">Fast (0.1s per move)</option>
                <option value="balanced">Balanced (0.2s per move)</option>
                <option value="deep">Deep (0.5s per move)</option>
              </select>
              <small>Higher depth = more accurate but slower</small>
            </div>
          </div>
        </div>

        <button 
          type="submit" 
          className="analyze-btn"
          disabled={!validation.isValid || isAnalyzing}
        >
          <span className={`btn-text ${isAnalyzing ? 'hidden' : ''}`}>
            🔍 Analyze My Games
          </span>
          <span className={`btn-loader ${isAnalyzing ? '' : 'hidden'}`}>
            ⏳ Analyzing...
          </span>
        </button>
      </form>
    </div>
  );
};

export default AnalysisForm; 