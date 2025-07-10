/**
 * MCB Main Application - Refactored
 * Uses modular architecture with state management and template helpers.
 */

// Cache DOM elements to avoid repeated queries
const DOMElements = {
    // Form elements
    usernameInput: null,
    analyzeBtn: null,
    gameCountSlider: null,
    gameCountValue: null,
    gameTypesSelect: null,
    ratingFilterSelect: null,
    analysisDepthSelect: null,
    gameResultSelect: null,
    blunderThresholdSlider: null,
    blunderThresholdValue: null,
    
    // Display elements
    progressSection: null,
    progressBar: null,
    progressText: null,
    progressLog: null,
    resultsSection: null,
    heroStat: null,
    analysisStats: null,
    blundersList: null,
    gamesByBlunders: null,
    
    // Initialize all elements
    init() {
        // Form elements
        this.usernameInput = document.getElementById('username');
        this.analyzeBtn = document.getElementById('analyzeBtn');
        this.gameCountSlider = document.getElementById('gameCount');
        this.gameCountValue = document.getElementById('gameCountValue');
        this.gameTypesSelect = document.getElementById('gameTypes');
        this.ratingFilterSelect = document.getElementById('ratingFilter');
        this.analysisDepthSelect = document.getElementById('analysisDepth');
        this.gameResultSelect = document.getElementById('gameResult');
        this.blunderThresholdSlider = document.getElementById('blunderThreshold');
        this.blunderThresholdValue = document.getElementById('blunderThresholdValue');
        
        // Display elements
        this.progressSection = document.getElementById('progressSection');
        this.progressBar = document.getElementById('progressBar');
        this.progressText = document.getElementById('progressText');
        this.progressLog = document.getElementById('progressLog');
        this.resultsSection = document.getElementById('resultsSection');
        this.heroStat = document.getElementById('heroStat');
        this.analysisStats = document.getElementById('analysisStats');
        this.blundersList = document.getElementById('blundersList');
        this.gamesByBlunders = document.getElementById('games-by-blunders');
    }
};

// UI Controller - handles all UI updates
const UIController = {
    /**
     * Update analyze button state
     */
    updateAnalyzeButton(analyzing) {
        const btnText = DOMElements.analyzeBtn?.querySelector('.btn-text');
        const btnLoader = DOMElements.analyzeBtn?.querySelector('.btn-loader');
        
        if (analyzing) {
            btnText?.classList.add('hidden');
            btnLoader?.classList.remove('hidden');
            if (DOMElements.analyzeBtn) DOMElements.analyzeBtn.disabled = true;
        } else {
            btnText?.classList.remove('hidden');
            btnLoader?.classList.add('hidden');
            if (DOMElements.analyzeBtn) DOMElements.analyzeBtn.disabled = false;
        }
    },

    /**
     * Show/hide progress section
     */
    showProgressSection() {
        DOMElements.progressSection?.classList.remove('hidden');
    },

    hideProgressSection() {
        DOMElements.progressSection?.classList.add('hidden');
    },

    /**
     * Show/hide results section
     */
    showResultsSection() {
        DOMElements.resultsSection?.classList.remove('hidden');
    },

    hideResultsSection() {
        DOMElements.resultsSection?.classList.add('hidden');
    },

    /**
     * Update progress bar
     */
    updateProgress(percentage) {
        if (DOMElements.progressBar) {
            DOMElements.progressBar.style.width = `${percentage}%`;
        }
        if (DOMElements.progressText) {
            DOMElements.progressText.textContent = `${Math.round(percentage)}%`;
        }
    },

    /**
     * Add progress log entry
     */
    addProgressLog(message) {
        if (!DOMElements.progressLog) return;
        
        const logEntry = document.createElement('div');
        logEntry.className = 'progress-log-entry';
        logEntry.innerHTML = MCBTemplates.progressLogEntry(message).trim();
        
        DOMElements.progressLog.appendChild(logEntry);
        DOMElements.progressLog.scrollTop = DOMElements.progressLog.scrollHeight;
    },

    /**
     * Reset progress to initial state
     */
    resetProgress() {
        this.updateProgress(0);
        if (DOMElements.progressLog) {
            DOMElements.progressLog.innerHTML = '';
        }
    },

    /**
     * Validate form and update button state
     */
    validateForm() {
        const validation = mcbState.validateSettings();
        if (DOMElements.analyzeBtn) {
            DOMElements.analyzeBtn.disabled = !validation.isValid || mcbState.analysis.isAnalyzing;
        }
    }
};

// Analysis Controller - handles analysis operations
const AnalysisController = {
    /**
     * Start analysis with current settings
     */
    async startAnalysis() {
        if (mcbState.analysis.isAnalyzing) return;
        
        const validation = mcbState.validateSettings();
        if (!validation.isValid) {
            alert(Object.values(validation.errors).filter(error => error).join('\n'));
            return;
        }
        
        try {
            // Generate session ID and update state
            const sessionId = this.generateSessionId();
            mcbState.updateAnalysis({
                sessionId: sessionId,
                isAnalyzing: true,
                currentSettings: mcbState.getAnalysisSettings()
            });
            
            // Update UI
            UIController.updateAnalyzeButton(true);
            UIController.showProgressSection();
            UIController.hideResultsSection();
            UIController.resetProgress();
            
            // Start progress tracking
            this.startProgressTracking(sessionId);
            
            // Send analysis request
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    ...mcbState.getAnalysisSettings()
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('Analysis started:', data);
            
        } catch (error) {
            console.error('Analysis failed:', error);
            this.handleAnalysisError(error.message);
        }
    },

    /**
     * Start progress tracking via Server-Sent Events
     */
    startProgressTracking(sessionId) {
        // Close existing connection
        if (mcbState.connection.eventSource) {
            mcbState.connection.eventSource.close();
        }
        
        const eventSource = new EventSource(`/api/progress/${sessionId}`);
        
        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleProgressUpdate(data);
            } catch (e) {
                console.error('Failed to parse progress data:', e);
            }
        };
        
        eventSource.onerror = (event) => {
            console.error('EventSource error:', event);
            if (eventSource.readyState === EventSource.CLOSED) {
                console.log('EventSource connection closed');
            }
        };
        
        mcbState.updateConnection({
            eventSource: eventSource,
            isConnected: true
        });
    },

    /**
     * Handle progress updates
     */
    handleProgressUpdate(data) {
        console.log('Progress update:', data);
        
        // Handle heartbeat
        if (data.heartbeat) {
            mcbState.updateConnection({ lastHeartbeat: Date.now() });
            return;
        }
        
        // Update progress bar
        if (data.percentage !== undefined) {
            UIController.updateProgress(data.percentage);
            mcbState.updateUI({ currentProgress: data.percentage });
        }
        
        // Add progress log entry
        if (data.message) {
            UIController.addProgressLog(data.message);
        }
        
        // Handle completion
        if (data.status === 'completed' && data.results) {
            this.handleAnalysisComplete(data.results);
        } else if (data.status === 'error') {
            this.handleAnalysisError(data.error || 'Unknown error occurred');
        }
    },

    /**
     * Handle analysis completion
     */
    handleAnalysisComplete(results) {
        console.log('Analysis completed:', results);
        
        mcbState.updateAnalysis({
            isAnalyzing: false,
            results: results
        });
        
        UIController.updateAnalyzeButton(false);
        
        // Close progress tracking
        if (mcbState.connection.eventSource) {
            mcbState.connection.eventSource.close();
            mcbState.updateConnection({
                eventSource: null,
                isConnected: false
            });
        }
        
        // Update progress to 100%
        UIController.updateProgress(100);
        UIController.addProgressLog('✅ Analysis completed!');
        
        // Show results
        setTimeout(() => {
            ResultsController.displayResults(results);
        }, 1000);
    },

    /**
     * Handle analysis errors
     */
    handleAnalysisError(errorMessage) {
        console.error('Analysis error:', errorMessage);
        
        mcbState.updateAnalysis({ isAnalyzing: false });
        UIController.updateAnalyzeButton(false);
        
        if (mcbState.connection.eventSource) {
            mcbState.connection.eventSource.close();
            mcbState.updateConnection({
                eventSource: null,
                isConnected: false
            });
        }
        
        UIController.addProgressLog(`❌ Error: ${errorMessage}`);
        alert(`Analysis failed: ${errorMessage}`);
    },

    /**
     * Generate session ID
     */
    generateSessionId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
    }
};

// Results Controller - handles result display
const ResultsController = {
    /**
     * Display analysis results
     */
    displayResults(results) {
        console.log('Displaying results:', results);
        
        // Hide progress and show results
        UIController.hideProgressSection();
        UIController.showResultsSection();
        
        // Update analysis stats
        if (DOMElements.analysisStats) {
            DOMElements.analysisStats.textContent = MCBTemplates.analysisStats(
                results.games_analyzed, 
                results.total_blunders
            );
        }
        
        // Display hero stat
        if (results.hero_stat && DOMElements.heroStat) {
            DOMElements.heroStat.innerHTML = MCBTemplates.heroStat(results.hero_stat);
        }
        
        // Display blunder breakdown
        if (results.blunder_breakdown && DOMElements.blundersList) {
            this.displayBlunderBreakdown(results.blunder_breakdown);
        }
        
        // Display games with blunders
        if (results.games_with_blunders && DOMElements.gamesByBlunders) {
            this.displayGamesWithBlunders(results.games_with_blunders);
        }
        
        // Cache results
        mcbState.updateCache({
            gamesWithBlunders: results.games_with_blunders || [],
            blunderData: results.blunder_breakdown || [],
            heroStat: results.hero_stat
        });
        
        // Also set global variable for backward compatibility with loadGameBlunders function
        window.gamesWithBlunders = results.games_with_blunders || [];
    },

    /**
     * Display blunder breakdown
     */
    displayBlunderBreakdown(breakdown) {
        if (!breakdown || breakdown.length === 0) {
            DOMElements.blundersList.innerHTML = MCBTemplates.noBlundersMessage();
            return;
        }
        
        const blundersHtml = breakdown.map((blunder, index) => 
            MCBTemplates.blunderItem(blunder, index)
        ).join('');
        
        DOMElements.blundersList.innerHTML = blundersHtml;
        
        // Add event listeners to toggle buttons
        this.attachBlunderToggleListeners();
    },

    /**
     * Display games with blunders
     */
    displayGamesWithBlunders(gamesWithBlunders) {
        if (!gamesWithBlunders || gamesWithBlunders.length === 0) {
            DOMElements.gamesByBlunders.innerHTML = '<div class="no-games-with-blunders">No games with blunders found</div>';
            return;
        }
        
        const gamesHtml = gamesWithBlunders.map(game => 
            MCBTemplates.gameBlunderItem(game)
        ).join('');
        
        DOMElements.gamesByBlunders.innerHTML = gamesHtml;
        
        // Add event listeners to toggle buttons
        this.attachGameToggleListeners();
    },

    /**
     * Attach event listeners to blunder toggle buttons
     */
    attachBlunderToggleListeners() {
        const toggleBtns = DOMElements.blundersList?.querySelectorAll('.blunder-toggle-btn');
        toggleBtns?.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const index = parseInt(btn.dataset.blunderIndex);
                const blunderData = mcbState.cache.blunderData[index];
                const blunderItem = btn.closest('.blunder-item');
                
                this.toggleBlunderDetails(blunderItem, blunderData, btn);
            });
        });
    },

    /**
     * Attach event listeners to game toggle buttons
     */
    attachGameToggleListeners() {
        const toggleBtns = DOMElements.gamesByBlunders?.querySelectorAll('.game-blunder-toggle-btn');
        toggleBtns?.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const gameNumber = parseInt(btn.dataset.gameNumber);
                const gameItem = btn.closest('.game-blunder-item');
                
                this.toggleGameBlunders(gameItem, gameNumber, btn);
            });
        });
    },

    /**
     * Toggle blunder details display
     */
    toggleBlunderDetails(element, blunderData, toggleBtn) {
        const detailsDiv = element.querySelector('.blunder-details');
        const toggleText = toggleBtn.querySelector('.blunder-toggle-text');
        const toggleIcon = toggleBtn.querySelector('.blunder-toggle-icon');
        const isCollapsed = detailsDiv.classList.contains('collapsed');
        
        if (isCollapsed) {
            // Expand
            detailsDiv.classList.remove('collapsed');
            element.classList.add('expanded');
            toggleText.textContent = 'Hide occurrences';
            toggleIcon.textContent = '▲';
            
            // Load details if not already loaded
            if (!detailsDiv.innerHTML.trim() || detailsDiv.innerHTML.includes('<!-- Details will be loaded dynamically -->')) {
                this.loadBlunderDetails(detailsDiv, blunderData);
            }
        } else {
            // Collapse
            detailsDiv.classList.add('collapsed');
            element.classList.remove('expanded');
            toggleText.textContent = 'Show occurrences';
            toggleIcon.textContent = '▼';
        }
    },

    /**
     * Toggle game blunders display
     */
    toggleGameBlunders(gameItem, gameNumber, toggleBtn) {
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
                this.loadGameBlunders(detailsDiv, gameNumber);
            }
        } else {
            // Collapse
            detailsDiv.classList.add('collapsed');
            toggleText.textContent = 'Show blunders';
            toggleIcon.textContent = '▼';
        }
    },

    /**
     * Load blunder details
     */
    loadBlunderDetails(container, blunderData) {
        if (!blunderData || !blunderData.all_occurrences) {
            container.innerHTML = '<div class="no-details">No data available</div>';
            return;
        }
        
        const occurrences = blunderData.all_occurrences;
        const headerHtml = MCBTemplates.blunderDetailsHeader(occurrences.length);
        const occurrencesHtml = occurrences.map(occurrence => 
            MCBTemplates.blunderOccurrence(occurrence)
        ).join('');
        
        container.innerHTML = headerHtml + occurrencesHtml;
    },

    /**
     * Load game blunders
     */
    loadGameBlunders(container, gameNumber) {
        const gamesWithBlunders = mcbState.cache.gamesWithBlunders;
        if (!gamesWithBlunders) {
            container.innerHTML = MCBTemplates.noGameDataMessage();
            return;
        }
        
        const gameData = gamesWithBlunders.find(g => g.game_number === gameNumber);
        if (!gameData || !gameData.blunders) {
            container.innerHTML = MCBTemplates.noGameBlundersMessage();
            return;
        }
        
        container.innerHTML = MCBTemplates.gameBlundersList(gameData.blunders, gameData.blunders.length);
    }
};

// Event Controller - handles DOM events
const EventController = {
    /**
     * Initialize all event listeners
     */
    init() {
        this.initializeFormEvents();
        this.initializeUIEvents();
        this.initializeStateEvents();
    },

    /**
     * Initialize form-related events
     */
    initializeFormEvents() {
        // Analyze button
        DOMElements.analyzeBtn?.addEventListener('click', () => {
            AnalysisController.startAnalysis();
        });
        
        // Enter key in username input
        DOMElements.usernameInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !mcbState.analysis.isAnalyzing) {
                AnalysisController.startAnalysis();
            }
        });
        
        // Form validation events
        DOMElements.usernameInput?.addEventListener('input', (e) => {
            mcbState.updateSettings({ username: e.target.value.trim() });
        });
        
        DOMElements.gameCountSlider?.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            mcbState.updateSettings({ gameCount: value });
        });
        
        DOMElements.gameTypesSelect?.addEventListener('change', (e) => {
            const selectedTypes = Array.from(e.target.selectedOptions).map(option => option.value);
            mcbState.updateSettings({ gameTypes: selectedTypes });
        });
        
        DOMElements.ratingFilterSelect?.addEventListener('change', (e) => {
            mcbState.updateSettings({ ratingFilter: e.target.value });
        });
        
        DOMElements.gameResultSelect?.addEventListener('change', (e) => {
            mcbState.updateSettings({ gameResult: e.target.value });
        });
        
        DOMElements.blunderThresholdSlider?.addEventListener('input', (e) => {
            mcbState.updateSettings({ blunderThreshold: parseInt(e.target.value) });
        });
        
        DOMElements.analysisDepthSelect?.addEventListener('change', (e) => {
            mcbState.updateSettings({ analysisDepth: e.target.value });
        });
    },

    /**
     * Initialize UI-related events
     */
    initializeUIEvents() {
        // Logo click to reset
        document.querySelector('.logo')?.addEventListener('click', () => {
            this.resetPage();
        });
        
        // Toggle sections - use header elements instead of just icons
        document.getElementById('blundersSectionHeader')?.addEventListener('click', () => {
            this.toggleBlundersSection();
        });
        
        document.getElementById('gamesByBlundersSectionHeader')?.addEventListener('click', () => {
            this.toggleGamesByBlundersSection();
        });
    },

    /**
     * Initialize state change listeners
     */
    initializeStateEvents() {
        // Listen for settings changes to update form validation
        mcbState.on('settingsChanged', () => {
            UIController.validateForm();
        });
        
        // Listen for analysis state changes to update UI
        mcbState.on('analysisStateChanged', (data) => {
            UIController.updateAnalyzeButton(data.current.isAnalyzing);
        });
    },

    /**
     * Reset page to initial state
     */
    resetPage() {
        mcbState.reset();
        UIController.validateForm();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    /**
     * Toggle blunders section
     */
    toggleBlundersSection() {
        const blundersContent = document.getElementById('blundersContent');
        const blundersToggleIcon = document.getElementById('blundersToggleIcon');
        const isCollapsed = blundersContent?.classList.contains('collapsed');
        
        if (isCollapsed) {
            blundersContent?.classList.remove('collapsed');
            if (blundersToggleIcon) {
                blundersToggleIcon.classList.add('rotated');
                blundersToggleIcon.textContent = '▲';
            }
        } else {
            blundersContent?.classList.add('collapsed');
            if (blundersToggleIcon) {
                blundersToggleIcon.classList.remove('rotated');
                blundersToggleIcon.textContent = '▼';
            }
        }
    },

    /**
     * Toggle games by blunders section
     */
    toggleGamesByBlundersSection() {
        const gamesByBlundersContent = document.getElementById('gamesByBlundersContent');
        const gamesByBlundersToggleIcon = document.getElementById('gamesByBlundersToggleIcon');
        const isCollapsed = gamesByBlundersContent?.classList.contains('collapsed');
        
        if (isCollapsed) {
            gamesByBlundersContent?.classList.remove('collapsed');
            if (gamesByBlundersToggleIcon) {
                gamesByBlundersToggleIcon.classList.add('rotated');
                gamesByBlundersToggleIcon.textContent = '▲';
            }
        } else {
            gamesByBlundersContent?.classList.add('collapsed');
            if (gamesByBlundersToggleIcon) {
                gamesByBlundersToggleIcon.classList.remove('rotated');
                gamesByBlundersToggleIcon.textContent = '▼';
            }
        }
    }
};

// Application initialization
document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 MCB Application Starting (Refactored)');
    
    // Initialize DOM elements cache
    DOMElements.init();
    
    // Initialize event handlers
    EventController.init();
    
    // Initial form validation
    UIController.validateForm();
    
    console.log('✅ MCB Application Ready');
});

// Error handling
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
}); 