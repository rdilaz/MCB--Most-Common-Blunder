/**
 * MCB Template Helpers Module
 * Reusable template functions to replace repetitive innerHTML string building.
 */

const MCBTemplates = {
    /**
     * Helper functions for common elements
     */
    gameTypeIcon: {
        'bullet': '🔥',
        'blitz': '⚡',
        'rapid': '🎯',
        'classical': '🏰',
        'daily': '📬',
        'unknown': '🎮'
    },

    /**
     * Format win probability drop
     */
    formatWinProbDrop(winProbDrop) {
        if (!winProbDrop || winProbDrop <= 0) return '';
        return `<span class="win-prob-drop">-${winProbDrop.toFixed(1)}% ↓</span>`;
    },

    /**
     * Format game type with proper capitalization
     */
    formatGameType(timeClass) {
        if (!timeClass || timeClass === 'unknown') return 'Unknown';
        return timeClass.charAt(0).toUpperCase() + timeClass.slice(1);
    },

    /**
     * Get game type icon
     */
    getGameTypeIcon(timeClass) {
        return this.gameTypeIcon[timeClass] || this.gameTypeIcon.unknown;
    },

    /**
     * Format blunder description with proper capitalization
     */
    formatBlunderDescription(description) {
        if (!description) return 'No description available';
        
        // Capitalize "your move" to "Your move"
        if (description.toLowerCase().startsWith('your move')) {
            return 'Y' + description.substring(1);
        }
        
        return description;
    },

    /**
     * Generate hero stat HTML
     */
    heroStat(heroStat) {
        const scoreText = heroStat.severity_score ? heroStat.severity_score.toFixed(1) : '--';
        
        return `
            <div class="hero-stat-header">
                <h4 id="heroStatTitle">🥇 #1 Most Common: ${heroStat.category}</h4>
                <div class="hero-stat-score">
                    <span id="heroStatScore">${scoreText}</span>
                    <div class="severity-tooltip">
                        <span class="tooltip-trigger"></span>
                        <div class="tooltip-content">
                            <strong>Severity Score</strong><br>
                            Measures how much this blunder type hurts your games.<br><br>
                            Higher scores = more frequent + more damaging mistakes.<br>
                            Based on how often you make it and average rating point loss.
                        </div>
                    </div>
                    <small>severity score</small>
                </div>
            </div>
            <div class="hero-stat-description">
                ${heroStat.description || heroStat.general_description || 'No description available'}
            </div>
            <div class="hero-stat-examples">
                ${this.heroStatExamples(heroStat.examples)}
            </div>
        `;
    },

    /**
     * Generate hero stat examples HTML
     */
    heroStatExamples(examples) {
        if (!examples || examples.length === 0) {
            return '<div class="hero-stat-example">🎯 Examples will appear here with more games analyzed</div>';
        }

        return examples.slice(0, 3).map(example => `
            <div class="hero-stat-example">
                🎯 Move ${example.move_number || 'Unknown'}: ${example.description || 'No description'}
            </div>
        `).join('');
    },

    /**
     * Generate blunder item HTML
     */
    blunderItem(blunder, index) {
        const rank = index + 1;
        const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
        const occurrenceText = blunder.frequency === 1 ? 'occurrence' : 'occurrences';
        
        return `
            <div class="blunder-item" data-blunder-index="${index}">
                <div class="blunder-item-header">
                    <div class="blunder-item-title">${medal} ${blunder.category}</div>
                    <div class="blunder-item-score">${blunder.severity_score ? blunder.severity_score.toFixed(1) : '--'}</div>
                </div>
                <div class="blunder-item-description">
                    ${blunder.description || blunder.general_description || 'No description available'}
                </div>
                <div class="blunder-item-stats">
                    <span class="blunder-stat"><strong>${blunder.frequency || 0}</strong> ${occurrenceText}</span>
                    <span class="blunder-stat"><strong>${blunder.avg_impact || 0}%</strong> avg impact</span>
                </div>
                <div class="blunder-toggle-section">
                    <button class="blunder-toggle-btn" data-blunder-index="${index}">
                        <span class="blunder-toggle-text">Show occurrences</span>
                        <span class="blunder-toggle-icon">▼</span>
                    </button>
                </div>
                <div class="blunder-details collapsed">
                    <!-- Details will be loaded dynamically -->
                </div>
            </div>
        `;
    },

    /**
     * Generate game blunder item HTML
     */
    gameBlunderItem(game) {
        const targetPlayer = game.target_player;
        const whiteDisplay = game.white === targetPlayer ? `<strong>${game.white}</strong>` : game.white;
        const blackDisplay = game.black === targetPlayer ? `<strong>${game.black}</strong>` : game.black;
        const gameTypeIcon = this.getGameTypeIcon(game.time_class);
        const ratingBadge = game.rated ? '🏆 Rated' : '🎮 Unrated';
        const blunderCount = game.blunders ? game.blunders.length : 0;
        
        return `
            <div class="game-blunder-item" data-game-number="${game.game_number}">
                <div class="game-blunder-header">
                    <div class="game-blunder-info">
                        <div class="game-players">
                            ${whiteDisplay} vs ${blackDisplay}
                        </div>
                        <div class="game-details">
                            <span class="game-meta">📅 ${game.date} • ${gameTypeIcon} ${this.formatGameType(game.time_class)} • ${ratingBadge}</span>
                        </div>
                    </div>
                    <div class="game-blunder-stats">
                        <div class="blunder-count">${blunderCount} blunder${blunderCount !== 1 ? 's' : ''}</div>
                        ${game.url ? `
                            <a href="${game.url}" target="_blank" class="game-link-small">
                                🔗 View
                            </a>
                        ` : '<span class="game-link-disabled">No link</span>'}
                    </div>
                </div>
                <div class="game-blunder-toggle">
                    <button class="game-blunder-toggle-btn" data-game-number="${game.game_number}">
                        <span class="toggle-text">Show blunders</span>
                        <span class="toggle-icon">▼</span>
                    </button>
                </div>
                <div class="game-blunder-details collapsed">
                    <!-- Blunder details will be loaded here -->
                </div>
            </div>
        `;
    },

    /**
     * Generate individual blunder HTML
     */
    individualBlunder(blunder) {
        return `
            <div class="individual-blunder">
                <div class="blunder-header">
                    <div class="blunder-move">
                        🎯 Move ${blunder.move_number || 'Unknown'}: ${blunder.category || 'Unknown'} ${this.formatWinProbDrop(blunder.win_prob_drop)}
                    </div>
                </div>
                <div class="blunder-description">
                    ${this.formatBlunderDescription(blunder.description)}
                </div>
                ${blunder.best_move ? `
                    <div class="blunder-best-move">
                        💡 <strong>Best move was:</strong> ${blunder.best_move}
                    </div>
                ` : ''}
            </div>
        `;
    },

    /**
     * Generate blunder occurrence HTML
     */
    blunderOccurrence(occurrence) {
        const gameNumber = occurrence.game_number || occurrence.game_index || 'Unknown';
        const whitePlayer = occurrence.game_white || 'Unknown';
        const blackPlayer = occurrence.game_black || 'Unknown';
        const gameDate = occurrence.game_date || 'Unknown date';
        const timeClass = occurrence.game_time_class || 'unknown';
        const gameUrl = occurrence.game_url || '';
        const isRated = occurrence.game_rated ? '🏆 Rated' : '🎮 Unrated';
        const targetPlayer = occurrence.target_player || '';
        
        // Highlight target player in bold
        const whiteDisplay = whitePlayer === targetPlayer ? `<strong>${whitePlayer}</strong>` : whitePlayer;
        const blackDisplay = blackPlayer === targetPlayer ? `<strong>${blackPlayer}</strong>` : blackPlayer;
        
        // Get game type icon
        const gameTypeIcon = this.getGameTypeIcon(timeClass);
        
        return `
            <div class="blunder-occurrence">
                <div class="blunder-occurrence-header">
                    <div class="occurrence-move">
                        🎯 Move ${occurrence.move_number || 'Unknown'} ${this.formatWinProbDrop(occurrence.win_prob_drop)}
                    </div>
                    <div class="occurrence-game-info">
                        Game #${gameNumber}: ${whiteDisplay} vs ${blackDisplay}
                    </div>
                    <div class="occurrence-game-meta">
                        <span class="game-meta-item">📅 ${gameDate} • ${gameTypeIcon} ${this.formatGameType(timeClass)} • ${isRated}</span>
                    </div>
                </div>
                <div class="blunder-occurrence-description">
                    ${this.formatBlunderDescription(occurrence.description)}
                </div>
                ${occurrence.best_move ? `
                    <div class="occurrence-best-move">
                        💡 <strong>Best move was:</strong> ${occurrence.best_move}
                    </div>
                ` : ''}
                ${gameUrl ? `
                    <div class="occurrence-game-link">
                        <a href="${gameUrl}" target="_blank" class="game-link-small">
                            🔗 View this game on Chess.com
                        </a>
                    </div>
                ` : '<div class="occurrence-game-link-disabled">⚠️ Game link not available</div>'}
            </div>
        `;
    },

    /**
     * Generate progress log entry HTML
     */
    progressLogEntry(message) {
        const timestamp = new Date().toLocaleTimeString();
        return `
            <div class="progress-log-entry">
                [${timestamp}] ${message}
            </div>
        `;
    },

    /**
     * Generate no blunders message
     */
    noBlundersMessage() {
        return '<div class="no-blunders">No blunders found! Great job! 🎉</div>';
    },

    /**
     * Generate no game blunders message
     */
    noGameBlundersMessage() {
        return '<div class="no-game-blunders">No blunders found for this game</div>';
    },

    /**
     * Generate no game data message
     */
    noGameDataMessage() {
        return '<div class="no-game-blunders">No game data available</div>';
    },

    /**
     * Generate analysis stats text
     */
    analysisStats(gamesAnalyzed, totalBlunders) {
        return `Analyzed ${gamesAnalyzed || 0} games • Found ${totalBlunders || 0} blunders`;
    },

    /**
     * Generate blunder details header
     */
    blunderDetailsHeader(occurrenceCount) {
        return `
            <div class="blunder-occurrences-header">
                ${occurrenceCount} Occurrence${occurrenceCount !== 1 ? 's' : ''} Found:
            </div>
        `;
    },

    /**
     * Generate game blunders list
     */
    gameBlundersList(blunders, blunderCount) {
        const blundersHtml = blunders.map(blunder => this.individualBlunder(blunder)).join('');
        
        return `
            <div class="game-blunders-list">
                <div class="game-blunders-header">
                    ${blunderCount} blunder${blunderCount !== 1 ? 's' : ''} found in chronological order:
                </div>
                ${blundersHtml}
            </div>
        `;
    }
};

// Export for use in other modules
window.MCBTemplates = MCBTemplates; 