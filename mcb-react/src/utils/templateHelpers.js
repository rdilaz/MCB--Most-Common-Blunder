// Template Helper Utilities (converted from MCBTemplates)

export const gameTypeIcon = {
  'bullet': '🔥',
  'blitz': '⚡',
  'rapid': '🎯',
  'classical': '🏰',
  'daily': '📬',
  'unknown': '🎮'
};

/**
 * Format win probability drop
 */
export const formatWinProbDrop = (winProbDrop) => {
  if (!winProbDrop || winProbDrop <= 0) return '';
  return `-${winProbDrop.toFixed(1)}% ↓`;
};

/**
 * Format game type with proper capitalization
 */
export const formatGameType = (timeClass) => {
  if (!timeClass || timeClass === 'unknown') return 'Unknown';
  return timeClass.charAt(0).toUpperCase() + timeClass.slice(1);
};

/**
 * Get game type icon
 */
export const getGameTypeIcon = (timeClass) => {
  return gameTypeIcon[timeClass] || gameTypeIcon.unknown;
};

/**
 * Format blunder description with proper capitalization
 */
export const formatBlunderDescription = (description) => {
  if (!description) return 'No description available';
  
  // Capitalize "your move" to "Your move"
  if (description.toLowerCase().startsWith('your move')) {
    return 'Y' + description.substring(1);
  }
  
  return description;
};

/**
 * Format analysis stats text
 */
export const formatAnalysisStats = (gamesAnalyzed, totalBlunders) => {
  return `Analyzed ${gamesAnalyzed || 0} games • Found ${totalBlunders || 0} blunders`;
};

/**
 * Create progress log entry data
 */
export const createProgressLogEntry = (message) => {
  return {
    message,
    timestamp: new Date().toLocaleTimeString()
  };
}; 