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
              Represents the impact of this type of blunder.<br /><br />
              Takes into account how many times the blunder occured
              and how much it impacted evaluation. <br /><br />
              Higher score = more frequent + more damaging mistakes.
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