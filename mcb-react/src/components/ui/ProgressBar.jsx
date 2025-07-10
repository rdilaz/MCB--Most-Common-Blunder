import React from 'react';
import { useMCB } from '../../context/MCBContext';

const ProgressBar = () => {
  const { ui } = useMCB();

  if (!ui.progressVisible) return null;

  return (
    <div className="progress-section">
      <h3>📊 Analysis Progress</h3>
      <div className="progress-container">
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${ui.currentProgress}%` }}
          ></div>
        </div>
        <div className="progress-text">{Math.round(ui.currentProgress)}%</div>
      </div>
      <div className="progress-log">
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