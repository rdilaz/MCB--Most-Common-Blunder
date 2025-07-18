import React, { useEffect, useRef } from 'react';
import { useMCB } from '../../context/MCBContext';

const ProgressBar = () => {
  const { ui, analysis } = useMCB();
  const progressLogRef = useRef(null);

  // Auto-scroll to bottom when new logs are added
  useEffect(() => {
    if (progressLogRef.current) {
      progressLogRef.current.scrollTop = progressLogRef.current.scrollHeight;
    }
  }, [ui.progressLogs]);

  if (!ui.progressVisible) return null;

  // Calculate upfront time estimate based on settings
  const calculateUpfrontEstimate = (settings) => {
    if (!settings) return 60; // fallback
    
    // Time per move based on analysis depth
    const depthTimes = {
      'fast': 0.05,     // 50ms per move
      'balanced': 0.08, // 80ms per move  
      'deep': 0.15      // 150ms per move
    };
    
    const timePerMove = depthTimes[settings.analysisDepth] || 0.08;
    const avgMovesPerGame = 40; // reasonable estimate
    const gameCount = settings.gameCount || 20;
    
    // Calculate analysis time
    const analysisTime = gameCount * avgMovesPerGame * timePerMove;
    
    // Add overhead for fetching games, engine setup, etc.
    const overhead = Math.min(15, gameCount * 0.5); // max 15s overhead
    
    return Math.round(analysisTime + overhead);
  };

  // Calculate estimated time completion
  const calculateEstimatedTime = () => {
    if (!analysis.currentSettings) return null;
    
    // Get upfront estimate
    const totalEstimated = calculateUpfrontEstimate(analysis.currentSettings);
    
    // If no progress yet, show full estimate
    if (ui.currentProgress <= 0) return totalEstimated;
    
    // Use progress to determine remaining time
    const progressRatio = ui.currentProgress / 100;
    const remaining = Math.max(0, totalEstimated * (1 - progressRatio));
    
    return Math.round(remaining);
  };

  const estimatedTimeLeft = calculateEstimatedTime();

  const formatTime = (seconds) => {
    if (seconds === null || seconds < 0) return '--';
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  return (
    <div className="progress-section">
      <h3>📊 Analysis Progress</h3>
      <div className="progress-container">
        <div className="progress-bar-wrapper">
          <div className="progress-percentage-top">{Math.round(ui.currentProgress)}%</div>
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${ui.currentProgress}%` }}
            ></div>
          </div>
          <div className="estimated-time-bottom">
            {estimatedTimeLeft !== null ? 
              `Est. ${formatTime(estimatedTimeLeft)} remaining` : 
              'Starting analysis...'
            }
          </div>
        </div>
      </div>
      <div className="progress-log" ref={progressLogRef}>
        {ui.progressLogs.map((log, index) => (
          <ProgressLogEntry key={index} log={log} />
        ))}
      </div>
    </div>
  );
};

const ProgressLogEntry = ({ log }) => {
  return (
    <div className="progress-log-entry">
      [{log.timestamp}] {log.message}
    </div>
  );
};

export default ProgressBar; 