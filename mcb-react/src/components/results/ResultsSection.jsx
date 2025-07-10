import React from 'react';
import { useMCB } from '../../context/MCBContext';
import { formatAnalysisStats } from '../../utils/templateHelpers';
import HeroStat from '../ui/HeroStat';
import BlunderItem from '../ui/BlunderItem';
import BlundersSection from './BlundersSection';
import GamesSection from './GamesSection';

const ResultsSection = () => {
  const { ui, analysis } = useMCB();

  if (!ui.resultsVisible || !analysis.results) return null;

  const { results } = analysis;

  return (
    <div className="results-section">
      <div className="results-header">
        <h3>🎯 Your Most Common Blunders</h3>
        <p className="analysis-stats">
          {formatAnalysisStats(results.games_analyzed, results.total_blunders)}
        </p>
      </div>

      {/* Hero Stat */}
      {results.hero_stat && (
        <HeroStat heroStat={results.hero_stat} />
      )}

      {/* Blunder Breakdown Section */}
      <BlundersSection blunders={results.blunder_breakdown || []} />

      {/* Games with Blunders Section */}
      <GamesSection games={results.games_with_blunders || []} />
    </div>
  );
};

export default ResultsSection; 