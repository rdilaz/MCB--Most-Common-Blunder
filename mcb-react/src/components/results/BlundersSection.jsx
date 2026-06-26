import React from 'react';
import BlunderItem from '../ui/BlunderItem';
import CollapsibleSection from '../ui/CollapsibleSection';

const BlundersSection = ({ blunders }) => {
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
    <CollapsibleSection
      title={<h4>📊 Blunders</h4>}
      containerClassName="other-blunders"
      headerClassName="blunders-section-header"
      contentClassName="blunders-content"
    >
      <div className="blunders-list">
        {blunders.map((blunder, index) => (
          <BlunderItem 
            key={index} 
            blunder={blunder} 
            index={index} 
          />
        ))}
      </div>
    </CollapsibleSection>
  );
};

export default BlundersSection;