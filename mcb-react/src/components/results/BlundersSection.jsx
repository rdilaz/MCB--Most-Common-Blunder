import React, { useState } from 'react';
import BlunderItem from '../ui/BlunderItem';

const BlundersSection = ({ blunders }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  const toggleCollapsed = () => {
    setIsExpanded(!isExpanded);
  };

  if (!blunders || blunders.length === 0) {
    return (
      <div className="other-blunders">
        <div className="blunders-section-header">
          <h4>📊 Blunders</h4>
        </div>
        <div className="no-blunders">No blunders found! Great job! 🎉</div>
      </div>
    );
  }

  return (
    <div className="other-blunders">
      <div className="blunders-section-header" onClick={() => setIsExpanded(!isExpanded)}>
        <h4>📊 Blunders</h4>
        <span className={`toggle-icon ${isExpanded ? 'rotated' : ''}`}>▼</span>
      </div>
      <div className={`blunders-content ${isExpanded ? '' : 'collapsed'}`}>
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