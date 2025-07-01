// Wait for DOM to be loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const analysisForm = document.getElementById('analysis-form');
    const usernameInput = document.getElementById('username-input');
    const loadingSection = document.getElementById('loading-section');
    const progressSection = document.getElementById('progress-section');
    const errorSection = document.getElementById('error-section');
    const errorMessage = document.getElementById('error-message');
    const resultsSection = document.getElementById('results-section');
    const toggleBlundersBtn = document.getElementById('toggle-blunders-btn');
    const blundersContainer = document.getElementById('blunders-container');

    // Progress elements
    const progressFill = document.getElementById('progress-fill');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressTime = document.getElementById('progress-time');
    const stepIcon = document.getElementById('step-icon');
    const stepMessage = document.getElementById('step-message');
    const progressLog = document.getElementById('progress-log');

    // State management
    let isBlundersVisible = false;
    let progressEventSource = null;
    let progressStartTime = null;

    // Step icons mapping
    const stepIcons = {
        'starting': '🚀',
        'fetching_games': '🌐',
        'engine_init': '🔧',
        'engine_ready': '✅',
        'reading_pgn': '📖',
        'analyzing_game': '🎯',
        'aggregating': '📊',
        'complete': '🎉',
        'error': '❌'
    };

    // Form submission handler
    analysisForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const username = usernameInput.value.trim();
        if (!username) {
            showError('Please enter a username');
            return;
        }

        await analyzePlayer(username);
    });

    // Toggle blunders visibility
    toggleBlundersBtn.addEventListener('click', function() {
        isBlundersVisible = !isBlundersVisible;
        
        if (isBlundersVisible) {
            blundersContainer.style.display = 'block';
            toggleBlundersBtn.textContent = 'Hide Individual Blunders';
        } else {
            blundersContainer.style.display = 'none';
            toggleBlundersBtn.textContent = 'Show All Individual Blunders';
        }
    });

    // Main analysis function with real-time progress
    async function analyzePlayer(username) {
        // Generate unique session ID
        const sessionId = `${username}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        showProgress();
        hideError();
        hideResults();
        
        // Start progress tracking immediately
        startProgressTracking(sessionId);

        try {
            // Start the analysis request with session ID
            const response = await fetch(`/api/analyze/${username}?session_id=${sessionId}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Analysis failed');
            }

            // Wait a moment to show completion, then display results
            setTimeout(() => {
                hideProgress();
                displayResults(data);
            }, 1500);
            
        } catch (error) {
            console.error('Analysis error:', error);
            hideProgress();
            showError(error.message || 'Failed to analyze games. Please try again.');
        }
    }

    // Progress tracking functions
    function showProgress() {
        progressSection.style.display = 'block';
        progressStartTime = Date.now();
        
        // Reset progress UI
        updateProgress(0, 'Starting analysis...', 'starting');
        clearProgressLog();
    }

    function hideProgress() {
        progressSection.style.display = 'none';
        if (progressEventSource) {
            progressEventSource.close();
            progressEventSource = null;
        }
    }

    function startProgressTracking(sessionId) {
        if (progressEventSource) {
            progressEventSource.close();
        }

        // Add a small delay to ensure the backend is ready
        setTimeout(() => {
            progressEventSource = new EventSource(`/api/progress/${sessionId}`);
            
            progressEventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.heartbeat) {
                        return; // Ignore heartbeat messages
                    }
                    
                    handleProgressUpdate(data);
                    
                } catch (error) {
                    console.error('Error parsing progress data:', error);
                }
            };

            progressEventSource.onerror = function(event) {
                console.error('Progress stream error:', event);
                // Don't close on error - let it reconnect automatically
            };
        }, 100);
    }

    function handleProgressUpdate(data) {
        const { step, message, progress, time_elapsed } = data;
        
        // Update progress bar and message
        updateProgress(progress || 0, message, step);
        
        // Add to progress log
        addProgressLogEntry(message, time_elapsed);
        
        // Handle completion
        if (step === 'complete') {
            setTimeout(() => {
                hideProgress();
            }, 2000); // Show completion for 2 seconds
        }
    }

    function updateProgress(percentage, message, step) {
        // Update progress bar
        progressFill.style.width = `${percentage}%`;
        progressPercentage.textContent = `${Math.round(percentage)}%`;
        
        // Update time
        if (progressStartTime) {
            const elapsed = (Date.now() - progressStartTime) / 1000;
            progressTime.textContent = `${elapsed.toFixed(1)}s elapsed`;
        }
        
        // Update step icon and message
        const icon = stepIcons[step] || '⏳';
        stepIcon.textContent = icon;
        stepIcon.className = `step-icon ${step}`;
        stepMessage.textContent = message;
    }

    function addProgressLogEntry(message, timeElapsed) {
        const entry = document.createElement('div');
        entry.className = 'progress-log-entry';
        entry.textContent = `[${timeElapsed ? timeElapsed.toFixed(1) + 's' : 'now'}] ${message}`;
        
        progressLog.appendChild(entry);
        
        // Auto-scroll to bottom
        progressLog.scrollTop = progressLog.scrollHeight;
        
        // Limit log entries to prevent overflow
        const entries = progressLog.querySelectorAll('.progress-log-entry');
        if (entries.length > 20) {
            entries[0].remove();
        }
    }

    function clearProgressLog() {
        progressLog.innerHTML = '';
    }

    // Display results
    function displayResults(data) {
        const { username, games_analyzed, summary, blunders } = data;

        // Update player name
        document.getElementById('player-name').textContent = username;

        // Update statistics
        document.getElementById('games-analyzed').textContent = games_analyzed;
        document.getElementById('total-blunders').textContent = summary.total_blunders;

        if (summary.total_blunders === 0) {
            // Handle case with no blunders
            displayNoBlunders(username);
        } else {
            // Display most common blunder
            displayMostCommonBlunder(summary.most_common_blunder);
            
            // Display category breakdown
            displayCategoryBreakdown(summary.category_breakdown);
            
            // Display individual blunders
            displayIndividualBlunders(blunders);
        }

        showResults();
    }

    // Display most common blunder
    function displayMostCommonBlunder(mostCommon) {
        document.getElementById('most-common-category').textContent = mostCommon.category;
        document.getElementById('most-common-percentage').textContent = `${mostCommon.percentage}%`;
        document.getElementById('most-common-example').textContent = mostCommon.general_description;
    }

    // Display category breakdown
    function displayCategoryBreakdown(categoryBreakdown) {
        const categoryList = document.getElementById('category-list');
        categoryList.innerHTML = '';

        // Sort categories by count (descending)
        const sortedCategories = Object.entries(categoryBreakdown)
            .sort(([,a], [,b]) => b - a);

        sortedCategories.forEach(([category, count]) => {
            const categoryItem = document.createElement('div');
            categoryItem.className = 'category-item';
            
            categoryItem.innerHTML = `
                <span class="category-name">${category}</span>
                <span class="category-count">${count}</span>
            `;
            
            categoryList.appendChild(categoryItem);
        });
    }

    // Display individual blunders
    function displayIndividualBlunders(blunders) {
        const cardsContainer = document.getElementById('blunder-cards-container');
        cardsContainer.innerHTML = '';

        blunders.forEach((blunder, index) => {
            const card = document.createElement('div');
            card.className = 'blunder-card';
            
            card.innerHTML = `
                <h4>${blunder.category}</h4>
                <p><strong>Move ${blunder.move_number}:</strong> ${blunder.description}</p>
                ${blunder.punishing_move ? `<p><strong>Punishing Move:</strong> Available</p>` : ''}
            `;
            
            cardsContainer.appendChild(card);
        });

        // Update toggle button text
        toggleBlundersBtn.textContent = `Show All Individual Blunders (${blunders.length})`;
    }

    // Display no blunders case
    function displayNoBlunders(username) {
        document.getElementById('most-common-category').textContent = 'No Blunders Found! 🎉';
        document.getElementById('most-common-percentage').textContent = '0%';
        document.getElementById('most-common-example').textContent = `Great job, ${username}! You played very well in the analyzed games.`;
        
        // Hide category breakdown and toggle section
        document.querySelector('.category-breakdown').style.display = 'none';
        document.querySelector('.toggle-section').style.display = 'none';
    }

    // UI State Management Functions
    function showLoading() {
        loadingSection.style.display = 'block';
    }

    function hideLoading() {
        loadingSection.style.display = 'none';
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorSection.style.display = 'block';
    }

    function hideError() {
        errorSection.style.display = 'none';
    }

    function showResults() {
        resultsSection.style.display = 'block';
    }

    function hideResults() {
        resultsSection.style.display = 'none';
        // Reset blunders visibility state
        isBlundersVisible = false;
        blundersContainer.style.display = 'none';
        
        // Show category breakdown and toggle section (in case they were hidden)
        const categoryBreakdown = document.querySelector('.category-breakdown');
        const toggleSection = document.querySelector('.toggle-section');
        if (categoryBreakdown) categoryBreakdown.style.display = 'block';
        if (toggleSection) toggleSection.style.display = 'block';
    }

    // Helper function to capitalize first letter
    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    // Cleanup function for when page is unloaded
    window.addEventListener('beforeunload', function() {
        if (progressEventSource) {
            progressEventSource.close();
        }
    });

    // Auto-focus on username input
    usernameInput.focus();
});
