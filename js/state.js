/**
 * MCB State Management Module
 * Centralized state management for the frontend application.
 * Replaces scattered global variables with a structured approach.
 */

class MCBState {
    constructor() {
        // Analysis state
        this.analysis = {
            sessionId: null,
            isAnalyzing: false,
            currentSettings: null,
            results: null
        };
        
        // UI state
        this.ui = {
            progressVisible: false,
            resultsVisible: false,
            currentProgress: 0,
            progressLogs: []
        };
        
        // Connection state
        this.connection = {
            eventSource: null,
            isConnected: false,
            lastHeartbeat: null
        };
        
        // Data cache
        this.cache = {
            gamesWithBlunders: [],
            blunderData: [],
            heroStat: null
        };
        
        // Settings state
        this.settings = {
            username: '',
            gameCount: 20,
            gameTypes: ['blitz', 'rapid'],
            ratingFilter: 'rated',
            gameResult: 'all',
            blunderThreshold: 15,
            analysisDepth: 'fast'
        };
        
        // Initialize event system
        this.listeners = new Map();
        this.initializeFromDOM();
    }
    
    /**
     * Initialize state from DOM values
     */
    initializeFromDOM() {
        try {
            // Get current form values
            const usernameInput = document.getElementById('username');
            const gameCountSlider = document.getElementById('gameCount');
            const gameTypesSelect = document.getElementById('gameTypes');
            const ratingFilterSelect = document.getElementById('ratingFilter');
            const gameResultSelect = document.getElementById('gameResult');
            const blunderThresholdSlider = document.getElementById('blunderThreshold');
            const analysisDepthSelect = document.getElementById('analysisDepth');
            
            if (usernameInput) this.settings.username = usernameInput.value.trim();
            if (gameCountSlider) this.settings.gameCount = parseInt(gameCountSlider.value);
            if (gameTypesSelect) {
                this.settings.gameTypes = Array.from(gameTypesSelect.selectedOptions).map(option => option.value);
            }
            if (ratingFilterSelect) this.settings.ratingFilter = ratingFilterSelect.value;
            if (gameResultSelect) this.settings.gameResult = gameResultSelect.value;
            if (blunderThresholdSlider) this.settings.blunderThreshold = parseInt(blunderThresholdSlider.value);
            if (analysisDepthSelect) this.settings.analysisDepth = analysisDepthSelect.value;
            
        } catch (error) {
            console.warn('Error initializing state from DOM:', error);
        }
    }
    
    /**
     * Update analysis state
     */
    updateAnalysis(updates) {
        const previousState = { ...this.analysis };
        this.analysis = { ...this.analysis, ...updates };
        this.emit('analysisStateChanged', { previous: previousState, current: this.analysis });
    }
    
    /**
     * Update UI state
     */
    updateUI(updates) {
        const previousState = { ...this.ui };
        this.ui = { ...this.ui, ...updates };
        this.emit('uiStateChanged', { previous: previousState, current: this.ui });
    }
    
    /**
     * Update connection state
     */
    updateConnection(updates) {
        const previousState = { ...this.connection };
        this.connection = { ...this.connection, ...updates };
        this.emit('connectionStateChanged', { previous: previousState, current: this.connection });
    }
    
    /**
     * Update settings
     */
    updateSettings(updates) {
        const previousState = { ...this.settings };
        this.settings = { ...this.settings, ...updates };
        this.emit('settingsChanged', { previous: previousState, current: this.settings });
        
        // Sync with DOM
        this.syncSettingsToDOM();
    }
    
    /**
     * Sync current settings to DOM elements
     */
    syncSettingsToDOM() {
        try {
            const usernameInput = document.getElementById('username');
            const gameCountSlider = document.getElementById('gameCount');
            const gameCountValue = document.getElementById('gameCountValue');
            const gameTypesSelect = document.getElementById('gameTypes');
            const ratingFilterSelect = document.getElementById('ratingFilter');
            const gameResultSelect = document.getElementById('gameResult');
            const blunderThresholdSlider = document.getElementById('blunderThreshold');
            const blunderThresholdValue = document.getElementById('blunderThresholdValue');
            const analysisDepthSelect = document.getElementById('analysisDepth');
            
            if (usernameInput) usernameInput.value = this.settings.username;
            if (gameCountSlider) gameCountSlider.value = this.settings.gameCount;
            if (gameCountValue) gameCountValue.textContent = this.settings.gameCount;
            if (ratingFilterSelect) ratingFilterSelect.value = this.settings.ratingFilter;
            if (gameResultSelect) gameResultSelect.value = this.settings.gameResult;
            if (blunderThresholdSlider) blunderThresholdSlider.value = this.settings.blunderThreshold;
            if (blunderThresholdValue) blunderThresholdValue.textContent = this.settings.blunderThreshold;
            if (analysisDepthSelect) analysisDepthSelect.value = this.settings.analysisDepth;
            
            // Handle multi-select for game types
            if (gameTypesSelect) {
                Array.from(gameTypesSelect.options).forEach(option => {
                    option.selected = this.settings.gameTypes.includes(option.value);
                });
            }
            
        } catch (error) {
            console.warn('Error syncing settings to DOM:', error);
        }
    }
    
    /**
     * Update cache data
     */
    updateCache(updates) {
        this.cache = { ...this.cache, ...updates };
        this.emit('cacheUpdated', { current: this.cache });
    }
    
    /**
     * Reset to initial state
     */
    reset() {
        // Reset analysis state
        this.updateAnalysis({
            sessionId: null,
            isAnalyzing: false,
            currentSettings: null,
            results: null
        });
        
        // Reset UI state
        this.updateUI({
            progressVisible: false,
            resultsVisible: false,
            currentProgress: 0,
            progressLogs: []
        });
        
        // Close connection
        if (this.connection.eventSource) {
            this.connection.eventSource.close();
        }
        this.updateConnection({
            eventSource: null,
            isConnected: false,
            lastHeartbeat: null
        });
        
        // Clear cache
        this.updateCache({
            gamesWithBlunders: [],
            blunderData: [],
            heroStat: null
        });
        
        // Reset settings to defaults
        this.updateSettings({
            username: '',
            gameCount: 20,
            gameTypes: ['blitz', 'rapid'],
            ratingFilter: 'rated',
            gameResult: 'all',
            blunderThreshold: 15,
            analysisDepth: 'fast'
        });
        
        this.emit('stateReset');
    }
    
    /**
     * Get current analysis settings for API request
     */
    getAnalysisSettings() {
        return {
            username: this.settings.username,
            gameCount: this.settings.gameCount,
            gameTypes: this.settings.gameTypes,
            ratingFilter: this.settings.ratingFilter,
            gameResult: this.settings.gameResult,
            blunderThreshold: this.settings.blunderThreshold,
            analysisDepth: this.settings.analysisDepth
        };
    }
    
    /**
     * Validate current settings
     */
    validateSettings() {
        const { username, gameTypes } = this.settings;
        return {
            isValid: username.length > 0 && gameTypes.length > 0,
            errors: {
                username: username.length === 0 ? 'Username is required' : null,
                gameTypes: gameTypes.length === 0 ? 'At least one game type must be selected' : null
            }
        };
    }
    
    /**
     * Event system methods
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }
    
    off(event, callback) {
        if (this.listeners.has(event)) {
            const callbacks = this.listeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }
    
    emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in event listener for ${event}:`, error);
                }
            });
        }
    }
    
    /**
     * Debug method to get current state
     */
    getState() {
        return {
            analysis: { ...this.analysis },
            ui: { ...this.ui },
            connection: { ...this.connection },
            cache: { ...this.cache },
            settings: { ...this.settings }
        };
    }
}

// Create global state instance
const mcbState = new MCBState();

// Export for use in other modules
window.mcbState = mcbState; 