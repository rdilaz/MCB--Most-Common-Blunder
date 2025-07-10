import React, { useState } from 'react';
import { formatBlunderDescription, formatWinProbDrop, getGameTypeIcon, formatGameType } from '../../utils/templateHelpers';

const BlunderItem = ({ blunder, index }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const rank = index + 1;
  const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
  const occurrenceText = blunder.frequency === 1 ? 'occurrence' : 'occurrences';

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <div className={`blunder-item ${isExpanded ? 'expanded' : ''}`} data-blunder-index={index}>
      <div className="blunder-item-header">
        <div className="blunder-item-title">{medal} {blunder.category}</div>
        <div className="blunder-item-score">{blunder.severity_score ? blunder.severity_score.toFixed(1) : '--'}</div>
      </div>
      <div className="blunder-item-description">
        {blunder.description || blunder.general_description || 'No description available'}
      </div>
      <div className="blunder-item-stats">
        <span className="blunder-stat"><strong>{blunder.frequency || 0}</strong> {occurrenceText}</span>
        <span className="blunder-stat"><strong>{blunder.avg_impact || 0}%</strong> avg impact</span>
      </div>
      <div className="blunder-toggle-section">
        <button className="blunder-toggle-btn" onClick={toggleExpanded}>
          <span className="blunder-toggle-text">
            {isExpanded ? 'Hide occurrences' : 'Show occurrences'}
          </span>
          <span className="blunder-toggle-icon">{isExpanded ? '▲' : '▼'}</span>
        </button>
      </div>
      <div className={`blunder-details ${isExpanded ? '' : 'collapsed'}`}>
        {isExpanded && <BlunderOccurrences occurrences={blunder.all_occurrences || blunder.examples || []} />}
      </div>
    </div>
  );
};

const BlunderOccurrences = ({ occurrences }) => {
  if (!occurrences || occurrences.length === 0) {
    return <div className="no-occurrences">No occurrences found</div>;
  }

  return (
    <div className="blunder-occurrences">
      <div className="blunder-occurrences-header">
        {occurrences.length} Occurrence{occurrences.length !== 1 ? 's' : ''} Found:
      </div>
      {occurrences.map((occurrence, index) => (
        <BlunderOccurrence key={index} occurrence={occurrence} />
      ))}
    </div>
  );
};

const BlunderOccurrence = ({ occurrence }) => {
  const gameNumber = occurrence.game_number || occurrence.game_index || 'Unknown';
  const whitePlayer = occurrence.game_white || 'Unknown';
  const blackPlayer = occurrence.game_black || 'Unknown';
  const gameDate = occurrence.game_date || 'Unknown date';
  const timeClass = occurrence.game_time_class || 'unknown';
  const gameUrl = occurrence.game_url || '';
  const isRated = occurrence.game_rated ? '🏆 Rated' : '🎮 Unrated';
  const targetPlayer = occurrence.target_player || '';
  
  // Highlight target player in bold
  const whiteDisplay = whitePlayer === targetPlayer ? whitePlayer : whitePlayer;
  const blackDisplay = blackPlayer === targetPlayer ? blackPlayer : blackPlayer;
  
  // Get game type icon
  const gameTypeIcon = getGameTypeIcon(timeClass);

  return (
    <div className="blunder-occurrence">
      <div className="blunder-occurrence-header">
        <div className="occurrence-move">
          🎯 Move {occurrence.move_number || 'Unknown'} {formatWinProbDrop(occurrence.win_prob_drop) && (
            <span className="win-prob-drop">{formatWinProbDrop(occurrence.win_prob_drop)}</span>
          )}
        </div>
        <div className="occurrence-game-info">
          Game #{gameNumber}: {whitePlayer === targetPlayer ? <strong>{whiteDisplay}</strong> : whiteDisplay} vs {blackPlayer === targetPlayer ? <strong>{blackDisplay}</strong> : blackDisplay}
        </div>
        <div className="occurrence-game-meta">
          <span className="game-meta-item">📅 {gameDate} • {gameTypeIcon} {formatGameType(timeClass)} • {isRated}</span>
        </div>
      </div>
      <div className="blunder-occurrence-description">
        {formatBlunderDescription(occurrence.description)}
      </div>
      {occurrence.best_move && (
        <div className="occurrence-best-move">
          💡 <strong>Best move was:</strong> {occurrence.best_move}
        </div>
      )}
      {gameUrl ? (
        <div className="occurrence-game-link">
          <a href={gameUrl} target="_blank" rel="noopener noreferrer" className="game-link-small">
            🔗 View this game on Chess.com
          </a>
        </div>
      ) : (
        <div className="occurrence-game-link-disabled">⚠️ Game link not available</div>
      )}
    </div>
  );
};

export default BlunderItem; 