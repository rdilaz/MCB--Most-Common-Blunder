import React from 'react';
import { formatBlunderDescription } from '../../utils/templateHelpers';

const BaseBlunder = ({ 
  blunder, 
  moveText, 
  winProbDrop, 
  headerDetails, 
  footerDetails, 
  containerClass = "individual-blunder" 
}) => {
  return (
    <div className={containerClass}>
      <div className={`${containerClass}-header`}>
        <div className="blunder-move occurrence-move">
          {moveText || `🎯 Move ${blunder.move_number || 'Unknown'}`}
          {winProbDrop && <span className="win-prob-drop">{winProbDrop}</span>}
        </div>
        {headerDetails}
      </div>
      <div className={`${containerClass}-description blunder-description`}>
        {formatBlunderDescription(blunder.description)}
      </div>
      {blunder.best_move && (
        <div className={`${containerClass}-best-move blunder-best-move occurrence-best-move`}>
          💡 <strong>Best move was:</strong> {blunder.best_move}
        </div>
      )}
      {footerDetails}
    </div>
  );
};

export default BaseBlunder;
