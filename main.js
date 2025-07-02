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
}

function displayHeroStat(heroStat) {
    heroStatTitle.textContent = `🥇 #1 Most Common: ${heroStat.category}`;
    heroStatScore.textContent = heroStat.score ? heroStat.score.toFixed(1) : '--';
    heroStatDescription.textContent = heroStat.description || heroStat.general_description || 'No description available';
    
    // Display examples if available
    if (heroStat.examples && heroStat.examples.length > 0) {
        const examplesHtml = heroStat.examples.slice(0, 3).map(example => `
            <div class="hero-stat-example">
                🎯 Game vs. ${example.opponent || 'Unknown'}: Move ${example.move_number} (${example.impact || 'impact unknown'})
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
    
    const blundersHtml = breakdown.map((blunder, index) => {
        const rank = index + 1;
        const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
        
        return `
            <div class="blunder-item">
                <div class="blunder-item-header">
                    <div class="blunder-item-title">${medal} ${blunder.category}</div>
                    <div class="blunder-item-score">${blunder.score ? blunder.score.toFixed(1) : '--'}</div>
                </div>
                <div class="blunder-item-description">
                    ${blunder.description || blunder.general_description || 'No description available'}
                </div>
                <div class="blunder-item-stats">
                    📊 ${blunder.frequency || 0} occurrences • 📉 ${blunder.avg_impact || 0}% avg impact
                </div>
            </div>
        `;
    }).join('');
    
    blundersList.innerHTML = blundersHtml;
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
