import React, { useState } from 'react';
import { useMCB } from '../../context/MCBContext';
import { useAnalysis } from '../../hooks/useAnalysis';
import Slider from '../ui/Slider';

const AnalysisForm = () => {
  const { settings, updateSettings, validateSettings } = useMCB();
  const { isAnalyzing, startAnalysis } = useAnalysis();
  const [isSettingsExpanded, setIsSettingsExpanded] = useState(false);

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

  // Handle Enter key in username input (was missing!)
  const handleUsernameKeyPress = (e) => {
    if (e.key === 'Enter' && !isAnalyzing) {
      startAnalysis();
    }
  };

  const toggleSettings = () => {
    setIsSettingsExpanded(!isSettingsExpanded);
  };

  const validation = validateSettings();

  return (
    <div className="input-section">
      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <label htmlFor="username">Chess.com Username</label>
          <input
            type="text"
            id="username"
            placeholder="Enter your Chess.com username"
            value={settings.username}
            onChange={(e) => handleInputChange('username', e.target.value)}
            onKeyPress={handleUsernameKeyPress}
            required
          />
        </div>

        {/* Analysis Settings Panel */}
        <div className={`settings-panel ${isSettingsExpanded ? 'expanded' : 'collapsed'}`}>
          <div 
            className="settings-header" 
            onClick={toggleSettings}
            style={{ cursor: 'pointer' }}
          >
            <h3>⚙️ Analysis Settings</h3>
            <span className="toggle-icon">{isSettingsExpanded ? '▲' : '▼'}</span>
          </div>
          <div className={`settings-content ${isSettingsExpanded ? '' : 'collapsed'}`}>
            <div className="settings-grid">
            <div className="setting-group">
              <label htmlFor="gameCount">
                Number of Games: <span id="gameCountValue">{settings.gameCount}</span>
              </label>
              <Slider
                id="gameCount"
                min={1}
                max={100}
                value={settings.gameCount}
                onChange={(e) => handleInputChange('gameCount', parseInt(e.target.value))}
              />
              <small>Analyze your most recent games (max 100)</small>
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
                Blunder Threshold: <span id="blunderThresholdValue">{settings.blunderThreshold}</span>%
              </label>
              <Slider
                id="blunderThreshold"
                min={5}
                max={30}
                value={settings.blunderThreshold}
                onChange={(e) => handleInputChange('blunderThreshold', parseInt(e.target.value))}
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
                <option value="fast">Fast (0.08s per move)</option>
                <option value="balanced">Balanced (0.15s per move)</option>
                <option value="deep">Deep (0.3s per move)</option>
              </select>
              <small>Higher depth = more accurate but slower</small>
            </div>
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