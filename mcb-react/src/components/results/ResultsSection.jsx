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

  const getAnalysisDuration = () => {
    if (analysis.results.analysis_time_seconds) {
      return analysis.results.analysis_time_seconds.toFixed(2);
    }
    if (ui.progressLogs && ui.progressLogs.length > 1) {
      const startTime = ui.progressLogs[0].rawTimestamp;
      const endTime = ui.progressLogs[ui.progressLogs.length - 1].rawTimestamp;
      return ((endTime - startTime) / 1000).toFixed(2);
    }
    return 'a few';
  };

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