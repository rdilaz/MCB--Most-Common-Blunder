import React, { useState } from 'react';
import GameBlunderItem from './GameBlunderItem';

const GamesSection = ({ games }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!games || games.length === 0) {
    return (
      <div className="games-by-blunders">
        <div className="games-by-blunders-header">
          <h4>🎯 Games</h4>
        </div>
        <div className="no-games-with-blunders">No games with blunders found</div>
      </div>
    );
  }

  return (
    <div className="games-by-blunders">
      <div className="games-by-blunders-header" onClick={() => setIsExpanded(!isExpanded)}>
        <h4>🎯 Games</h4>
        <span className={`toggle-icon ${isExpanded ? 'rotated' : ''}`}>▼</span>
      </div>
      <div className={`games-by-blunders-content ${isExpanded ? '' : 'collapsed'}`}>
        <p className="games-by-blunders-subtitle">
          Click on any game to see its specific blunders in chronological order
        </p>
        <div className="games-by-blunders-list">
          {games.map((game, index) => (
            <GameBlunderItem 
              key={game.game_number || index} 
              game={game} 
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default GamesSection; 