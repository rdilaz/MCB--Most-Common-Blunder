// Global variables
let sessionId = null;
let eventSource = null;
let isAnalyzing = false;

// DOM Elements
const usernameInput = document.getElementById('username');
const analyzeBtn = document.getElementById('analyzeBtn');
const gameCountSlider = document.getElementById('gameCount');
const gameCountValue = document.getElementById('gameCountValue');
const gameTypesSelect = document.getElementById('gameTypes');
const ratingFilterSelect = document.getElementById('ratingFilter');
const analysisDepthSelect = document.getElementById('analysisDepth');
const progressSection = document.getElementById('progressSection');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');
const progressLog = document.getElementById('progressLog');
const resultsSection = document.getElementById('resultsSection');
const heroStat = document.getElementById('heroStat');
const heroStatTitle = document.getElementById('heroStatTitle');
const heroStatScore = document.getElementById('heroStatScore');
const heroStatDescription = document.getElementById('heroStatDescription');
const heroStatExamples = document.getElementById('heroStatExamples');
const analysisStats = document.getElementById('analysisStats');
const blundersList = document.getElementById('blundersList');
const gamesList = document.getElementById('gamesList');
const gamesContent = document.getElementById('gamesContent');
const gamesToggleIcon = document.getElementById('gamesToggleIcon');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    updateGameCountDisplay();
});

function initializeEventListeners() {
    // Analyze button
    analyzeBtn.addEventListener('click', handleAnalyzeClick);
    
    // Enter key in username input
    usernameInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !isAnalyzing) {
            handleAnalyzeClick();
        }
    });
    
    // Game count slider
    gameCountSlider.addEventListener('input', updateGameCountDisplay);
    
    // Settings validation
    usernameInput.addEventListener('input', validateForm);
    gameTypesSelect.addEventListener('change', validateForm);
}

function updateGameCountDisplay() {
    gameCountValue.textContent = gameCountSlider.value;
}

function validateForm() {
    const username = usernameInput.value.trim();
    const selectedGameTypes = Array.from(gameTypesSelect.selectedOptions);
    
    const isValid = username.length > 0 && selectedGameTypes.length > 0;
    analyzeBtn.disabled = !isValid || isAnalyzing;
}

function handleAnalyzeClick() {
    if (isAnalyzing) return;
    
    const username = usernameInput.value.trim();
    if (!username) {
        alert('Please enter a Chess.com username');
        return;
    }
    
    const selectedGameTypes = Array.from(gameTypesSelect.selectedOptions).map(option => option.value);
    if (selectedGameTypes.length === 0) {
        alert('Please select at least one game type');
        return;
    }
    
    const analysisSettings = {
        username: username,
        gameCount: parseInt(gameCountSlider.value),
        gameTypes: selectedGameTypes,
        ratingFilter: ratingFilterSelect.value,
        analysisDepth: analysisDepthSelect.value
    };
    
    startAnalysis(analysisSettings);
}

function startAnalysis(settings) {
    isAnalyzing = true;
    sessionId = generateSessionId();
    
    // Update UI state
    updateAnalyzeButton(true);
    showProgressSection();
    hideResultsSection();
    resetProgress();
    
    // Log analysis start
    addProgressLog(`🚀 Starting analysis for ${settings.username}`);
    addProgressLog(`⚙️ Settings: ${settings.gameCount} games, ${settings.gameTypes.join(', ')}, ${settings.ratingFilter}, ${settings.analysisDepth} depth`);
    
    // Start server-sent events for progress tracking
    startProgressTracking();
    
    // Send analysis request
    fetch('/api/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            session_id: sessionId,
            ...settings
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Analysis started:', data);
    })
    .catch(error => {
        console.error('Analysis failed:', error);
        handleAnalysisError(error.message);
    });
}

function startProgressTracking() {
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource(`/api/progress/${sessionId}`);
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleProgressUpdate(data);
        } catch (e) {
            console.error('Failed to parse progress data:', e);
        }
    };
    
    eventSource.onerror = function(event) {
        console.error('EventSource error:', event);
        if (eventSource.readyState === EventSource.CLOSED) {
            console.log('EventSource connection closed');
        }
    };
}

function handleProgressUpdate(data) {
    console.log('Progress update:', data);
    
    // Handle heartbeat
    if (data.heartbeat) {
        return;
    }
    
    // Update progress bar
    if (data.percentage !== undefined) {
        updateProgress(data.percentage);
    }
    
    // Add progress log entry
    if (data.message) {
        addProgressLog(data.message);
    }
    
    // Handle completion
    if (data.status === 'completed' && data.results) {
        handleAnalysisComplete(data.results);
    } else if (data.status === 'error') {
        handleAnalysisError(data.error || 'Unknown error occurred');
    }
}

function handleAnalysisComplete(results) {
    console.log('Analysis completed:', results);
    
    isAnalyzing = false;
    updateAnalyzeButton(false);
    
    // Close progress tracking
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    // Update progress to 100%
    updateProgress(100);
    addProgressLog('✅ Analysis completed!');
    
    // Show results
    setTimeout(() => {
        displayResults(results);
    }, 1000);
}

function handleAnalysisError(errorMessage) {
    console.error('Analysis error:', errorMessage);
    
    isAnalyzing = false;
    updateAnalyzeButton(false);
    
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    addProgressLog(`❌ Error: ${errorMessage}`);
    alert(`Analysis failed: ${errorMessage}`);
}

function displayResults(results) {
    console.log('Displaying results:', results);
    
    // Hide progress and show results
    hideProgressSection();
    showResultsSection();
    
    // Update analysis stats
    analysisStats.textContent = `Analyzed ${results.games_analyzed || 0} games • Found ${results.total_blunders || 0} blunders`;
    
    if (results.hero_stat) {
        displayHeroStat(results.hero_stat);
    }
    
    if (results.games_list) {
        displayGamesList(results.games_list);
    }
    
    if (results.blunder_breakdown) {
        displayBlunderBreakdown(results.blunder_breakdown);
    } else if (results.blunders) {
        // Fallback for single-game format
        displayLegacyBlunders(results.blunders);
    }
    
    // NEW: Display games with blunders breakdown
    if (results.games_with_blunders) {
        displayGamesWithBlunders(results.games_with_blunders);
    }
    
    // Store game data globally for access
    window.gamesWithBlunders = results.games_with_blunders || [];
}

function displayHeroStat(heroStat) {
    heroStatTitle.textContent = `🥇 #1 Most Common: ${heroStat.category}`;
    
    // Add severity score with tooltip
    const scoreText = heroStat.severity_score ? heroStat.severity_score.toFixed(1) : '--';
    heroStatScore.innerHTML = `
        ${scoreText}
        <div class="severity-tooltip">
            <span class="tooltip-trigger">?</span>
            <div class="tooltip-content">
                <strong>Severity Score</strong><br>
                Calculated as: Frequency × Category Weight × Average Impact<br><br>
                <strong>Category Weights:</strong><br>
                • Checkmate: 3.0<br>
                • Hanging Pieces: 2.5<br>
                • Forks/Exchanges: 2.0<br>
                • Pins/Material: 1.5-1.8<br>
                • General Mistakes: 1.0
            </div>
        </div>
    `;
    
    heroStatDescription.textContent = heroStat.description || heroStat.general_description || 'No description available';
    
    // Display examples if available
    if (heroStat.examples && heroStat.examples.length > 0) {
        const examplesHtml = heroStat.examples.slice(0, 3).map(example => `
            <div class="hero-stat-example">
                🎯 Move ${example.move_number || 'Unknown'}: ${example.description || 'No description'}
            </div>
        `).join('');
        heroStatExamples.innerHTML = examplesHtml;
    } else {
        heroStatExamples.innerHTML = '<div class="hero-stat-example">🎯 Examples will appear here with more games analyzed</div>';
    }
}

function displayGamesList(games) {
    if (!games || games.length === 0) {
        gamesList.innerHTML = '<div class="no-games">No games data available</div>';
        return;
    }
    
    const gamesHtml = games.map(game => {
        // Determine which player was analyzed (highlight in bold)
        const targetPlayer = game.target_player;
        const whiteDisplay = game.white === targetPlayer ? `<strong>${game.white}</strong>` : game.white;
        const blackDisplay = game.black === targetPlayer ? `<strong>${game.black}</strong>` : game.black;
        
        // Format game type and rating
        const gameTypeIcon = getGameTypeIcon(game.time_class);
        const ratingBadge = game.rated ? '🏆 Rated' : '🎮 Unrated';
        
        return `
            <div class="game-item">
                <div class="game-info">
                    <div class="game-players">
                        ${whiteDisplay} vs ${blackDisplay}
                    </div>
                    <div class="game-details">
                        <span class="game-meta">📅 ${game.date}</span>
                        <span class="game-meta">${gameTypeIcon} ${game.time_class}</span>
                        <span class="game-meta">${ratingBadge}</span>
                    </div>
                </div>
                ${game.url ? `
                    <a href="${game.url}" target="_blank" class="game-link">
                        🔗 View Game
                    </a>
                ` : '<span class="game-link-disabled">No link</span>'}
            </div>
        `;
    }).join('');
    
    gamesList.innerHTML = gamesHtml;
}

function displayGamesWithBlunders(gamesWithBlunders) {
    const gamesByBlundersContainer = document.getElementById('games-by-blunders');
    if (!gamesByBlundersContainer) {
        console.warn('games-by-blunders container not found');
        return;
    }
    
    if (!gamesWithBlunders || gamesWithBlunders.length === 0) {
        gamesByBlundersContainer.innerHTML = '<div class="no-games-with-blunders">No games with blunders found</div>';
        return;
    }
    
    const gamesHtml = gamesWithBlunders.map(game => {
        const targetPlayer = game.target_player;
        const whiteDisplay = game.white === targetPlayer ? `<strong>${game.white}</strong>` : game.white;
        const blackDisplay = game.black === targetPlayer ? `<strong>${game.black}</strong>` : game.black;
        const gameTypeIcon = getGameTypeIcon(game.time_class);
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
                            <span class="game-meta">📅 ${game.date}</span>
                            <span class="game-meta">${gameTypeIcon} ${game.time_class}</span>
                            <span class="game-meta">${ratingBadge}</span>
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
    }).join('');
    
    gamesByBlundersContainer.innerHTML = gamesHtml;
    
    // Add event listeners to toggle buttons
    const toggleBtns = gamesByBlundersContainer.querySelectorAll('.game-blunder-toggle-btn');
    toggleBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const gameNumber = parseInt(this.dataset.gameNumber);
            const gameItem = this.closest('.game-blunder-item');
            toggleGameBlunders(gameItem, gameNumber, this);
        });
    });
}

function getGameTypeIcon(timeClass) {
    switch(timeClass) {
        case 'bullet': return '🔥';
        case 'blitz': return '⚡';
        case 'rapid': return '🎯';
        case 'classical': return '🏰';
        case 'daily': return '📬';
        default: return '🎮';
    }
}

function displayBlunderBreakdown(breakdown) {
    if (!breakdown || breakdown.length === 0) {
        blundersList.innerHTML = '<div class="no-blunders">No blunders found! Great job! 🎉</div>';
        return;
    }
    
    // Store blunder data globally for click handlers
    window.blunderData = breakdown;
    
    const blundersHtml = breakdown.map((blunder, index) => {
        const rank = index + 1;
        const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
        
        // Fix grammar: "1 occurrence" vs "2 occurrences"
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
    }).join('');
    
    blundersList.innerHTML = blundersHtml;
    
    // Add click event listeners to toggle buttons
    const toggleBtns = blundersList.querySelectorAll('.blunder-toggle-btn');
    toggleBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            // Prevent event bubbling
            e.stopPropagation();
            
            const index = parseInt(this.dataset.blunderIndex);
            const blunderData = window.blunderData[index];
            const blunderItem = this.closest('.blunder-item');
            
            console.log('Blunder toggle clicked:', index, blunderData);
            toggleBlunderDetails(blunderItem, blunderData, this);
        });
    });
}

function displayLegacyBlunders(blunders) {
    // Fallback for single-game analysis format
    if (!blunders || blunders.length === 0) {
        blundersList.innerHTML = '<div class="no-blunders">No blunders found! Great job! 🎉</div>';
        return;
    }
    
    // Group blunders by category for legacy format
    const grouped = {};
    blunders.forEach(blunder => {
        const category = blunder.category || 'Unknown';
        if (!grouped[category]) {
            grouped[category] = [];
        }
        grouped[category].push(blunder);
    });
    
    // Display most common as hero stat
    const categories = Object.keys(grouped);
    if (categories.length > 0) {
        const mostCommon = categories.reduce((a, b) => 
            grouped[a].length > grouped[b].length ? a : b
        );
        
        heroStatTitle.textContent = `🥇 Most Common: ${mostCommon}`;
        heroStatScore.textContent = grouped[mostCommon].length;
        
        // Use the general description from blunder categories
        const firstBlunder = grouped[mostCommon][0];
        heroStatDescription.textContent = firstBlunder.general_description || firstBlunder.description || 'No description available';
        
        // Show examples
        const examplesHtml = grouped[mostCommon].slice(0, 3).map(blunder => `
            <div class="hero-stat-example">
                🎯 Move ${blunder.move_number}: ${blunder.description}
            </div>
        `).join('');
        heroStatExamples.innerHTML = examplesHtml;
    }
    
    // Display all categories
    const blundersHtml = categories.map((category, index) => {
        const count = grouped[category].length;
        const rank = index + 1;
        const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
        
        return `
            <div class="blunder-item">
                <div class="blunder-item-header">
                    <div class="blunder-item-title">${medal} ${category}</div>
                    <div class="blunder-item-score">${count}</div>
                </div>
                <div class="blunder-item-description">
                    Found ${count} instance${count !== 1 ? 's' : ''} of this blunder type
                </div>
            </div>
        `;
    }).join('');
    
    blundersList.innerHTML = blundersHtml;
}

// UI Helper Functions
function updateAnalyzeButton(analyzing) {
    const btnText = analyzeBtn.querySelector('.btn-text');
    const btnLoader = analyzeBtn.querySelector('.btn-loader');
    
    if (analyzing) {
        btnText.classList.add('hidden');
        btnLoader.classList.remove('hidden');
        analyzeBtn.disabled = true;
    } else {
        btnText.classList.remove('hidden');
        btnLoader.classList.add('hidden');
        analyzeBtn.disabled = false;
    }
}

function showProgressSection() {
    progressSection.classList.remove('hidden');
}

function hideProgressSection() {
    progressSection.classList.add('hidden');
}

function showResultsSection() {
    resultsSection.classList.remove('hidden');
}

function hideResultsSection() {
    resultsSection.classList.add('hidden');
}

function resetProgress() {
    updateProgress(0);
    progressLog.innerHTML = '';
}

function updateProgress(percentage) {
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = `${Math.round(percentage)}%`;
}

function addProgressLog(message) {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = document.createElement('div');
    logEntry.className = 'progress-log-entry';
    logEntry.textContent = `[${timestamp}] ${message}`;
    
    progressLog.appendChild(logEntry);
    progressLog.scrollTop = progressLog.scrollHeight;
}

// Toggle games section
function toggleGamesSection() {
    const isCollapsed = gamesContent.classList.contains('collapsed');
    
    if (isCollapsed) {
        gamesContent.classList.remove('collapsed');
        gamesToggleIcon.classList.add('rotated');
        gamesToggleIcon.textContent = '▲';
    } else {
        gamesContent.classList.add('collapsed');
        gamesToggleIcon.classList.remove('rotated');
        gamesToggleIcon.textContent = '▼';
    }
}

// Toggle blunders section
function toggleBlundersSection() {
    const blundersContent = document.getElementById('blundersContent');
    const blundersToggleIcon = document.getElementById('blundersToggleIcon');
    const isCollapsed = blundersContent.classList.contains('collapsed');
    
    if (isCollapsed) {
        blundersContent.classList.remove('collapsed');
        blundersToggleIcon.classList.add('rotated');
        blundersToggleIcon.textContent = '▲';
    } else {
        blundersContent.classList.add('collapsed');
        blundersToggleIcon.classList.remove('rotated');
        blundersToggleIcon.textContent = '▼';
    }
}

// Toggle games by blunders section
function toggleGamesByBlundersSection() {
    const gamesByBlundersContent = document.getElementById('gamesByBlundersContent');
    const gamesByBlundersToggleIcon = document.getElementById('gamesByBlundersToggleIcon');
    const isCollapsed = gamesByBlundersContent.classList.contains('collapsed');
    
    if (isCollapsed) {
        gamesByBlundersContent.classList.remove('collapsed');
        gamesByBlundersToggleIcon.classList.add('rotated');
        gamesByBlundersToggleIcon.textContent = '▲';
    } else {
        gamesByBlundersContent.classList.add('collapsed');
        gamesByBlundersToggleIcon.classList.remove('rotated');
        gamesByBlundersToggleIcon.textContent = '▼';
    }
}

// Toggle game blunders for individual games
function toggleGameBlunders(gameItem, gameNumber, toggleBtn) {
    const detailsDiv = gameItem.querySelector('.game-blunder-details');
    const toggleText = toggleBtn.querySelector('.toggle-text');
    const toggleIcon = toggleBtn.querySelector('.toggle-icon');
    const isCollapsed = detailsDiv.classList.contains('collapsed');
    
    if (isCollapsed) {
        // Expand
        detailsDiv.classList.remove('collapsed');
        toggleText.textContent = 'Hide blunders';
        toggleIcon.textContent = '▲';
        
        // Load blunders for this game
        if (!detailsDiv.innerHTML.trim() || detailsDiv.innerHTML.includes('<!-- Blunder details will be loaded here -->')) {
            loadGameBlunders(detailsDiv, gameNumber);
        }
    } else {
        // Collapse
        detailsDiv.classList.add('collapsed');
        toggleText.textContent = 'Show blunders';
        toggleIcon.textContent = '▼';
    }
}

// Load blunders for a specific game
function loadGameBlunders(container, gameNumber) {
    if (!window.gamesWithBlunders) {
        container.innerHTML = '<div class="no-game-blunders">No game data available</div>';
        return;
    }
    
    const gameData = window.gamesWithBlunders.find(g => g.game_number === gameNumber);
    if (!gameData || !gameData.blunders) {
        container.innerHTML = '<div class="no-game-blunders">No blunders found for this game</div>';
        return;
    }
    
    const blundersHtml = gameData.blunders.map((blunder, index) => {
        return `
            <div class="individual-blunder">
                <div class="blunder-header">
                    <div class="blunder-move">
                        🎯 Move ${blunder.move_number || 'Unknown'}: ${blunder.category || 'Unknown'}
                    </div>
                </div>
                <div class="blunder-description">
                    ${formatBlunderDescription(blunder)}
                </div>
                ${blunder.best_move ? `
                    <div class="blunder-best-move">
                        💡 <strong>Best move was:</strong> ${blunder.best_move}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
    
    container.innerHTML = `
        <div class="game-blunders-list">
            <div class="game-blunders-header">
                ${gameData.blunders.length} blunder${gameData.blunders.length !== 1 ? 's' : ''} found in chronological order:
            </div>
            ${blundersHtml}
        </div>
    `;
}

// Toggle blunder details with button
function toggleBlunderDetails(element, blunderData, toggleBtn) {
    const detailsDiv = element.querySelector('.blunder-details');
    const toggleText = toggleBtn.querySelector('.blunder-toggle-text');
    const toggleIcon = toggleBtn.querySelector('.blunder-toggle-icon');
    const isCollapsed = detailsDiv.classList.contains('collapsed');
    
    console.log('Toggle details:', isCollapsed ? 'expanding' : 'collapsing', blunderData);
    
    if (isCollapsed) {
        // Expand
        detailsDiv.classList.remove('collapsed');
        element.classList.add('expanded');
        toggleText.textContent = 'Hide occurrences';
        toggleIcon.textContent = '▲';
        toggleIcon.classList.add('rotated');
        console.log('Expanding blunder details');
        
        // Load details if not already loaded
        if (!detailsDiv.innerHTML.trim() || detailsDiv.innerHTML.includes('<!-- Details will be loaded dynamically -->')) {
            console.log('Loading blunder details...');
            loadBlunderDetails(detailsDiv, blunderData);
        }
    } else {
        // Collapse
        detailsDiv.classList.add('collapsed');
        element.classList.remove('expanded');
        toggleText.textContent = 'Show occurrences';
        toggleIcon.textContent = '▼';
        toggleIcon.classList.remove('rotated');
        console.log('Collapsing blunder details');
    }
}

// Load detailed blunder occurrences with game links
function loadBlunderDetails(container, blunderData) {
    console.log('Loading details for:', blunderData);
    
    if (!blunderData) {
        container.innerHTML = '<div class="no-details">No data available</div>';
        return;
    }
    
    // Check if we have occurrence data
    if (!blunderData.all_occurrences || blunderData.all_occurrences.length === 0) {
        // Try to create synthetic occurrences from the main data
        const occurrences = [];
        
        // If we have frequency data, create that many occurrences
        if (blunderData.frequency && blunderData.frequency > 0) {
            for (let i = 0; i < blunderData.frequency; i++) {
                occurrences.push({
                    move_number: `Unknown`,
                    description: blunderData.description || blunderData.general_description || 'No detailed description available',
                    game_index: i > 0 ? Math.floor(i / 5) + 1 : 1 // Rough estimation
                });
            }
        } else {
            // Fallback: create one occurrence
            occurrences.push({
                move_number: 'Unknown',
                description: blunderData.description || blunderData.general_description || 'No detailed description available',
                game_index: 1
            });
        }
        
        blunderData.all_occurrences = occurrences;
    }
    
    const occurrences = blunderData.all_occurrences;
    const detailsHtml = `
        <div class="blunder-occurrences-header">
            ${occurrences.length} Occurrence${occurrences.length !== 1 ? 's' : ''} Found:
        </div>
        ${occurrences.map((occurrence, index) => {
            // Enhanced display with game information and links
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
            const gameTypeIcon = getGameTypeIcon(timeClass);
            
            return `
                <div class="blunder-occurrence">
                    <div class="blunder-occurrence-header">
                        <div class="occurrence-move">
                            🎯 Move ${occurrence.move_number || 'Unknown'}
                        </div>
                        <div class="occurrence-game-info">
                            Game #${gameNumber}: ${whiteDisplay} vs ${blackDisplay}
                        </div>
                        <div class="occurrence-game-meta">
                            <span class="game-meta-item">📅 ${gameDate}</span>
                            <span class="game-meta-item">${gameTypeIcon} ${timeClass}</span>
                            <span class="game-meta-item">${isRated}</span>
                        </div>
                    </div>
                    <div class="blunder-occurrence-description">
                        ${formatBlunderDescription(occurrence)}
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
        }).join('')}
    `;
    
    container.innerHTML = detailsHtml;
    console.log('Details loaded successfully with game links');
}

// Format blunder description with proper capitalization
function formatBlunderDescription(occurrence) {
    let description = occurrence.description || 'No description available';
    
    // Capitalize "your move" to "Your move"
    if (description.toLowerCase().startsWith('your move')) {
        description = 'Y' + description.substring(1);
    }
    
    return description;
}

// Utility Functions
function generateSessionId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
}

// Error Handling
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
});

window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
});
