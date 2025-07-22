import React from 'react';
import { useMCB } from '../../context/MCBContext';

const SettingsSummary = ({ onSummaryClick }) => {
  const { settings } = useMCB();
  const {
    username,
    gameCount,
    gameTypes,
    ratingFilter,
    gameResult,
    blunderThreshold,
    analysisDepth
  } = settings;

  const depthMap = {
    fast: '0.08s',
    balanced: '0.15s',
    deep: '0.3s'
  };

  const allGameTypes = ['bullet', 'blitz', 'rapid', 'classical'];

  const renderUsername = () => {
    if (username) {
      return <span className="highlight" onClick={() => onSummaryClick('username')}>{username}'s</span>;
    }
    return <span className="highlight-missing" onClick={() => onSummaryClick('username')}>{'{username}'}'s</span>;
  };

  const renderGameCount = () => {
    if (gameCount === 1) return null;
    return <span className="highlight" onClick={() => onSummaryClick('gameCount')}>{gameCount}</span>;
  };

  const renderGameTypes = () => {
    if (gameTypes.length === 0 || gameTypes.length === allGameTypes.length) {
      return null;
    }
    const connector = gameCount === 1 ? 'or' : '&';
    let gameTypesString;
    if (gameTypes.length === 1) {
      gameTypesString = gameTypes[0];
    } else if (gameTypes.length === 2) {
      gameTypesString = `${gameTypes[0]} ${connector} ${gameTypes[1]}`;
    } else {
      const last = gameTypes[gameTypes.length - 1];
      const rest = gameTypes.slice(0, -1).join(', ');
      gameTypesString = `${rest}, ${connector} ${last}`;
    }
    return <> <span className="highlight" onClick={() => onSummaryClick('gameTypes')}>{gameTypesString}</span></>;
  };

  const renderRatingFilter = () => {
    if (ratingFilter === 'all') {
      return null;
    }
    const filterText = ratingFilter === 'rated' ? 'rated' : 'non-rated';
    return <> <span className="highlight" onClick={() => onSummaryClick('ratingFilter')}>{filterText}</span></>;
  };

  const renderGameResult = () => {
    const gameNoun = gameCount === 1 ? 'game' : 'games';
    if (gameResult === 'all') {
      return ` ${gameNoun},`;
    }
    const resultText = gameResult === 'wins' ? 'that resulted in a win' : 'that resulted in a loss';
    return <> {gameNoun} <span className="highlight" onClick={() => onSummaryClick('gameResult')}>{resultText}</span>,</>;
  };
  
  const renderAnalysisDepth = () => {
    return <span className="highlight" onClick={() => onSummaryClick('analysisDepth')}>{depthMap[analysisDepth]} per move</span>;
  };

  const renderBlunderThreshold = () => {
    return <span className="highlight" onClick={() => onSummaryClick('blunderThreshold')}>{blunderThreshold}%</span>;
  };

  return (
    <div className="settings-summary">
      Analyze {renderUsername()} {renderGameCount()} most recent
      {renderRatingFilter()}
      {renderGameTypes()}
      {renderGameResult()} with a depth of {renderAnalysisDepth()}, to find all moves that resulted in a {renderBlunderThreshold()} drop in win probability.
    </div>
  );
};

export default SettingsSummary; 