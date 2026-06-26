import React from 'react';
import { useMCB } from '../../context/MCBContext';
import HeroStat from '../ui/HeroStat';
import GamesSection from './GamesSection';
import BlundersSection from './BlundersSection';

const ResultsSection = () => {
  const { analysis, ui } = useMCB();

  if (!analysis.results) {
    return null;
  }



  const gameNoun = analysis.results.games_analyzed === 1 ? 'game' : 'games';

  return (
    <div className="results-section">
      {/* Hero Stat - The Most Common Blunder */}
      {analysis.results.hero_stat && <HeroStat heroStat={analysis.results.hero_stat} />}

      {/* Other Blunders */}
      {analysis.results.blunder_breakdown && <BlundersSection blunders={analysis.results.blunder_breakdown} />}

      {/* Games By Blunders */}
      {analysis.results.games_with_blunders && <GamesSection games={analysis.results.games_with_blunders} />}
    </div>
  );
};

export default ResultsSection; 