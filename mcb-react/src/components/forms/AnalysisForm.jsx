import React, { useState, useRef, useEffect } from 'react';
import { useMCB } from '../../context/MCBContext';
import { useAnalysis } from '../../hooks/useAnalysis';
import Slider from '../ui/Slider';
import DeveloperMode from './DeveloperMode';
import SettingsSummary from '../ui/SettingsSummary';

const AnalysisForm = () => {
  const { settings, updateSettings, validateSettings } = useMCB();
  const { isAnalyzing, startAnalysis } = useAnalysis();
  const [isSettingsExpanded, setIsSettingsExpanded] = useState(false);
  const [openDropdowns, setOpenDropdowns] = useState({
    ratingFilter: false,
    gameResult: false,
    analysisDepth: false
  });
  const [activeSetting, setActiveSetting] = useState(null);

  const usernameRef = useRef(null);
  const gameCountRef = useRef(null);
  const gameTypesRef = useRef(null);
  const ratingFilterRef = useRef(null);
  const gameResultRef = useRef(null);
  const blunderThresholdRef = useRef(null);
  const analysisDepthRef = useRef(null);

  const refs = {
    username: usernameRef,
    gameCount: gameCountRef,
    gameTypes: gameTypesRef,
    ratingFilter: ratingFilterRef,
    gameResult: gameResultRef,
    blunderThreshold: blunderThresholdRef,
    analysisDepth: analysisDepthRef
  };

  const handleSummaryClick = (settingId) => {
    if (settingId !== 'username') {
      setIsSettingsExpanded(true);
    }
    
    setActiveSetting(settingId);

    const elementRef = refs[settingId];
    if (elementRef && elementRef.current) {
      setTimeout(() => {
        elementRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
        if (settingId === 'username') {
          usernameRef.current.focus();
        }
      }, 300); // Wait for panel to expand
    }
  };

  useEffect(() => {
    if (activeSetting) {
      const timer = setTimeout(() => {
        setActiveSetting(null);
      }, 1500); // Highlight for 1.5 seconds
      return () => clearTimeout(timer);
    }
  }, [activeSetting]);

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

  const handleUsernameKeyPress = (e) => {
    if (e.key === 'Enter' && !isAnalyzing) {
      startAnalysis();
    }
  };

  const toggleSettings = () => {
    setIsSettingsExpanded(!isSettingsExpanded);
  };

  const handleDropdownClick = (dropdownId) => {
    setOpenDropdowns(prev => ({
      ...prev,
      [dropdownId]: !prev[dropdownId]
    }));
  };

  const handleDropdownBlur = (dropdownId) => {
    setTimeout(() => {
      setOpenDropdowns(prev => ({
        ...prev,
        [dropdownId]: false
      }));
    }, 150);
  };

  const validation = validateSettings();

  return (
    <div className="input-section">
      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <input
            type="text"
            id="username"
            ref={usernameRef}
            placeholder="Enter your Chess.com username"
            value={settings.username}
            onChange={(e) => handleInputChange('username', e.target.value)}
            onKeyPress={handleUsernameKeyPress}
            required
          />
        </div>

        <div className={`settings-panel ${isSettingsExpanded ? 'expanded' : 'collapsed'}`}>
          <div 
            className="settings-header" 
            onClick={toggleSettings}
            style={{ cursor: 'pointer' }}
          >
            <h3>⚙️ Settings</h3>
            <span className="toggle-icon">{isSettingsExpanded ? '▲' : '▼'}</span>
          </div>
          <div className={`settings-content ${isSettingsExpanded ? '' : 'collapsed'}`}>
            <div className="settings-grid">
              <div className={`setting-group ${activeSetting === 'gameCount' ? 'active' : ''}`} ref={gameCountRef}>
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

              <div className={`setting-group ${activeSetting === 'gameTypes' ? 'active' : ''}`} ref={gameTypesRef}>
                <label htmlFor="gameTypes">Game Types</label>
                <div className="game-types-list">
                  {[
                    { value: 'bullet', label: 'Bullet (1-2 min)', img: '/bullet_8341453.png' },
                    { value: 'blitz', label: 'Blitz (3-5 min)', img: '/bolt_6771066.png' },
                    { value: 'rapid', label: 'Rapid (10-15 min)', img: '/timer_6771110.png' },
                    { value: 'classical', label: 'Classical (30+ min)', img: '/sun_553402.png' },
                  ].map(type => (
                    <label key={type.value} style={{ display: 'flex', alignItems: 'center', marginBottom: 6, cursor: 'pointer', gap: 8 }}>
                      <input
                        type="checkbox"
                        value={type.value}
                        checked={settings.gameTypes.includes(type.value)}
                        onChange={e => {
                          const checked = e.target.checked;
                          const newTypes = checked
                            ? [...settings.gameTypes, type.value]
                            : settings.gameTypes.filter(t => t !== type.value);
                          updateSettings({ gameTypes: newTypes });
                        }}
                        style={{ marginRight: 6 }}
                      />
                      <img src={type.img} alt={type.value} style={{ width: '1.3em', height: '1.3em', objectFit: 'contain', marginRight: 6 }} />
                      {type.label}
                    </label>
                  ))}
                </div>
              </div>

              <div className={`setting-group ${activeSetting === 'ratingFilter' ? 'active' : ''}`} ref={ratingFilterRef}>
                <label htmlFor="ratingFilter">Rating Filter</label>
                <div className="custom-dropdown">
                  <select 
                    id="ratingFilter"
                    value={settings.ratingFilter}
                    onChange={(e) => handleInputChange('ratingFilter', e.target.value)}
                    onMouseDown={() => handleDropdownClick('ratingFilter')}
                    onBlur={() => handleDropdownBlur('ratingFilter')}
                  >
                    <option value="all">All Games</option>
                    <option value="rated">Rated Games Only</option>
                    <option value="unrated">Unrated Games Only</option>
                  </select>
                  <span className={`dropdown-triangle ${openDropdowns.ratingFilter ? 'rotated' : ''}`}>▼</span>
                </div>
              </div>

              <div className={`setting-group ${activeSetting === 'gameResult' ? 'active' : ''}`} ref={gameResultRef}>
                <label htmlFor="gameResult">Game Results</label>
                <div className="custom-dropdown">
                  <select 
                    id="gameResult"
                    value={settings.gameResult}
                    onChange={(e) => handleInputChange('gameResult', e.target.value)}
                    onMouseDown={() => handleDropdownClick('gameResult')}
                    onBlur={() => handleDropdownBlur('gameResult')}
                  >
                    <option value="all">All Games</option>
                    <option value="wins">Wins Only</option>
                    <option value="losses">Losses Only</option>
                  </select>
                  <span className={`dropdown-triangle ${openDropdowns.gameResult ? 'rotated' : ''}`}>▼</span>
                </div>
                <small>Filter by game outcome</small>
              </div>

              <div className={`setting-group ${activeSetting === 'blunderThreshold' ? 'active' : ''}`} ref={blunderThresholdRef}>
                <label htmlFor="blunderThreshold">
                  Blunder Threshold: <span id="blunderThresholdValue">{settings.blunderThreshold}</span>%
                </label>
                <Slider
                  id="blunderThreshold"
                  min={5}
                  max={40}
                  value={settings.blunderThreshold}
                  onChange={(e) => handleInputChange('blunderThreshold', parseInt(e.target.value))}
                />
                <small>Win probability drop % to be considered a blunder</small>
              </div>

              <div className={`setting-group ${activeSetting === 'analysisDepth' ? 'active' : ''}`} ref={analysisDepthRef}>
                <label htmlFor="analysisDepth">Analysis Depth</label>
                <div className="custom-dropdown">
                  <select 
                    id="analysisDepth"
                    value={settings.analysisDepth}
                    onChange={(e) => handleInputChange('analysisDepth', e.target.value)}
                    onMouseDown={() => handleDropdownClick('analysisDepth')}
                    onBlur={() => handleDropdownBlur('analysisDepth')}
                  >
                    <option value="fast">Fast (0.08s per move)</option>
                    <option value="balanced">Balanced (0.15s per move)</option>
                    <option value="deep">Deep (0.3s per move)</option>
                  </select>
                  <span className={`dropdown-triangle ${openDropdowns.analysisDepth ? 'rotated' : ''}`}>▼</span>
                </div>
                <small>Higher depth = more accurate but slower</small>
              </div>
            </div>
          </div>
        </div>

        <SettingsSummary onSummaryClick={handleSummaryClick} />

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

      <DeveloperMode />
    </div>
  );
};

export default AnalysisForm;