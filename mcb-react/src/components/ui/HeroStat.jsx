import React from 'react';
import { formatBlunderDescription } from '../../utils/templateHelpers';

const HeroStat = ({ heroStat }) => {
  if (!heroStat) return null;

  const scoreText = heroStat.severity_score ? heroStat.severity_score.toFixed(1) : '--';

  return (
    <div className="hero-stat">
      <div className="hero-stat-header">
        <h4 id="heroStatTitle">🥇 #1 Most Common: {heroStat.category}</h4>
        <div className="hero-stat-score">
          <span id="heroStatScore">{scoreText}</span>
          <div className="severity-tooltip">
            <span className="tooltip-trigger"></span>
            <div className="tooltip-content">
              <strong>Severity Score</strong><br />
              Frequency × Weight × Impact<br /><br />
              <strong>Weights:</strong> Checkmate (3.0) • Hanging (2.5) • Forks (2.0) • Material (1.5-1.8) • General (1.0)
            </div>
          </div>
          <small>severity score</small>
        </div>
      </div>
      <div className="hero-stat-description">
        {heroStat.description || heroStat.general_description || 'No description available'}
      </div>
      <div className="hero-stat-examples">
        <HeroStatExamples examples={heroStat.examples} />
      </div>
    </div>
  );
};

const HeroStatExamples = ({ examples }) => {
  if (!examples || examples.length === 0) {
    return (
      <div className="hero-stat-example">
        🎯 Examples will appear here with more games analyzed
      </div>
    );
  }

  return (
    <>
      {examples.slice(0, 3).map((example, index) => (
        <div key={index} className="hero-stat-example">
          🎯 Move {example.move_number || 'Unknown'}: {example.description || 'No description'}
        </div>
      ))}
    </>
  );
};

export default HeroStat; 