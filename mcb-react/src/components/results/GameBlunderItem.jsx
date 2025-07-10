import React, { useState } from 'react';
import { getGameTypeIcon, formatGameType, formatBlunderDescription } from '../../utils/templateHelpers';
import { useMCB } from '../../context/MCBContext';

const GameBlunderItem = ({ game }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const targetPlayer = game.target_player;
  const gameTypeIcon = getGameTypeIcon(game.time_class);
  const ratingBadge = game.rated ? '🏆 Rated' : '🎮 Unrated';
  const blunderCount = game.blunders ? game.blunders.length : 0;

  return (
    <div className="game-blunder-item" data-game-number={game.game_number}>
      <div className="game-blunder-header">
        <div className="game-blunder-info">
          <div className="game-players">
            {game.white === targetPlayer ? (
              <><strong>{game.white}</strong> vs {game.black}</>
            ) : (
              <>{game.white} vs <strong>{game.black}</strong></>
            )}
          </div>
          <div className="game-details">
            <span className="game-meta">
              📅 {game.date} • {gameTypeIcon} {formatGameType(game.time_class)} • {ratingBadge}
            </span>
          </div>
        </div>
        <div className="game-blunder-stats">
          <div className="blunder-count">
            {blunderCount} blunder{blunderCount !== 1 ? 's' : ''}
          </div>
          {game.url ? (
            <a href={game.url} target="_blank" rel="noopener noreferrer" className="game-link-small">
              🔗 View
            </a>
          ) : (
            <span className="game-link-disabled">No link</span>
          )}
        </div>
      </div>
      <div className="game-blunder-toggle">
        <button className="game-blunder-toggle-btn" onClick={toggleExpanded}>
          <span className="toggle-text">
            {isExpanded ? 'Hide blunders' : 'Show blunders'}
          </span>
          <span className="toggle-icon">{isExpanded ? '▲' : '▼'}</span>
        </button>
      </div>
      <div className={`game-blunder-details ${isExpanded ? '' : 'collapsed'}`}>
        {isExpanded && <GameBlunders gameNumber={game.game_number} blunders={game.blunders} />}
      </div>
    </div>
  );
};

const GameBlunders = ({ gameNumber, blunders }) => {
  const { cache } = useMCB();

  // Handle case where blunders are not directly provided (mirrors original loadGameBlunders)
  let actualBlunders = blunders;
  
  if (!actualBlunders && cache.gamesWithBlunders) {
    const gameData = cache.gamesWithBlunders.find(g => g.game_number === gameNumber);
    actualBlunders = gameData?.blunders;
  }

  if (!actualBlunders || actualBlunders.length === 0) {
    return <div className="no-game-blunders">No blunders found for this game</div>;
  }

  return (
    <div className="game-blunders-list">
      <div className="game-blunders-header">
        {actualBlunders.length} blunder{actualBlunders.length !== 1 ? 's' : ''} found in chronological order:
      </div>
      {actualBlunders.map((blunder, index) => (
        <IndividualBlunder key={index} blunder={blunder} />
      ))}
    </div>
  );
};

const IndividualBlunder = ({ blunder }) => {
  return (
    <div className="individual-blunder">
      <div className="blunder-header">
        <div className="blunder-move">
          🎯 Move {blunder.move_number || 'Unknown'}: {blunder.category || 'Unknown'}
          {blunder.win_prob_drop && (
            <span className="win-prob-drop"> -{blunder.win_prob_drop.toFixed(1)}% ↓</span>
          )}
        </div>
      </div>
      <div className="blunder-description">
        {formatBlunderDescription(blunder.description)}
      </div>
      {blunder.best_move && (
        <div className="blunder-best-move">
          💡 <strong>Best move was:</strong> {blunder.best_move}
        </div>
      )}
    </div>
  );
};

export default GameBlunderItem; 