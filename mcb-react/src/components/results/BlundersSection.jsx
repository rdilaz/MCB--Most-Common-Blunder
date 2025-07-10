import React, { useState } from 'react';
import BlunderItem from '../ui/BlunderItem';

const BlundersSection = ({ blunders }) => {
  const [isCollapsed, setIsCollapsed] = useState(true);

  const toggleCollapsed = () => {
    setIsCollapsed(!isCollapsed);
  };

  if (!blunders || blunders.length === 0) {
    return (
      <div className="other-blunders">
        <div className="blunders-section-header">
          <h4>📊 Blunder by Severity</h4>
        </div>
        <div className="no-blunders">No blunders found! Great job! 🎉</div>
      </div>
    );
  }

  return (
    <div className="other-blunders">
      <div 
        className="blunders-section-header" 
        onClick={toggleCollapsed}
        style={{ cursor: 'pointer' }}
      >
        <h4>📊 Blunder by Severity</h4>
        <span className="toggle-icon">{isCollapsed ? '▼' : '▲'}</span>
      </div>
      <div className={`blunders-content ${isCollapsed ? 'collapsed' : ''}`}>
        <div className="blunders-list">
          {blunders.map((blunder, index) => (
            <BlunderItem 
              key={index} 
              blunder={blunder} 
              index={index} 
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default BlundersSection; 