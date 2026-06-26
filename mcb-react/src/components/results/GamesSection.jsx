import React from 'react';
import GameBlunderItem from './GameBlunderItem';
import CollapsibleSection from '../ui/CollapsibleSection';

const GamesSection = ({ games }) => {
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
    <CollapsibleSection
      title={<h4>🎯 Games</h4>}
      containerClassName="games-by-blunders"
      headerClassName="games-by-blunders-header"
      contentClassName="games-by-blunders-content"
    >
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
    </CollapsibleSection>
  );
};

export default GamesSection;