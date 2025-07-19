import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';

// Initial state that mirrors the original MCBState structure
const initialState = {
  // Analysis state
  analysis: {
    sessionId: null,
    isAnalyzing: false,
    currentSettings: null,
    results: null
  },
  
  // UI state
  ui: {
    progressVisible: false,
    resultsVisible: false,
    currentProgress: 0,
    progressLogs: []
  },
  
  // Connection state
  connection: {
    eventSource: null,
    isConnected: false,
    lastHeartbeat: null
  },
  
  // Data cache
  cache: {
    gamesWithBlunders: [],
    blunderData: [],
    heroStat: null
  },
  
  // Settings state
  settings: {
    username: '',
    gameCount: 20,
    gameTypes: ['blitz', 'rapid'],
    ratingFilter: 'rated',
    gameResult: 'all',
    blunderThreshold: 10,
    analysisDepth: 'balanced'
  }
};

// Action types
const ActionTypes = {
  UPDATE_ANALYSIS: 'UPDATE_ANALYSIS',
  UPDATE_UI: 'UPDATE_UI', 
  UPDATE_UI_FUNCTION: 'UPDATE_UI_FUNCTION',
  UPDATE_CONNECTION: 'UPDATE_CONNECTION',
  UPDATE_CACHE: 'UPDATE_CACHE',
  UPDATE_SETTINGS: 'UPDATE_SETTINGS',
  RESET_STATE: 'RESET_STATE'
};

// Reducer function that handles state updates
function mcbReducer(state, action) {
  switch (action.type) {
    case ActionTypes.UPDATE_ANALYSIS:
      return {
        ...state,
        analysis: { ...state.analysis, ...action.payload }
      };
      
    case ActionTypes.UPDATE_UI:
      return {
        ...state,
        ui: { ...state.ui, ...action.payload }
      };
      
    case ActionTypes.UPDATE_UI_FUNCTION:
      return {
        ...state,
        ui: action.payload(state.ui)
      };
      
    case ActionTypes.UPDATE_CONNECTION:
      return {
        ...state,
        connection: { ...state.connection, ...action.payload }
      };
      
    case ActionTypes.UPDATE_CACHE:
      return {
        ...state,
        cache: { ...state.cache, ...action.payload }
      };
      
    case ActionTypes.UPDATE_SETTINGS:
      return {
        ...state,
        settings: { ...state.settings, ...action.payload }
      };
      
    case ActionTypes.RESET_STATE:
      return { ...initialState };
      
    default:
      return state;
  }
}

// Create the context
const MCBContext = createContext();

// Custom hook to use the MCB context
export const useMCB = () => {
  const context = useContext(MCBContext);
  if (!context) {
    throw new Error('useMCB must be used within an MCBProvider');
  }
  return context;
};

// Provider component
export const MCBProvider = ({ children }) => {
  const [state, dispatch] = useReducer(mcbReducer, initialState);

  // Action creators that mirror the original MCBState methods
  const updateAnalysis = useCallback((updates) => {
    dispatch({ type: ActionTypes.UPDATE_ANALYSIS, payload: updates });
  }, []);

  const updateUI = useCallback((updates) => {
    if (typeof updates === 'function') {
      dispatch({ type: ActionTypes.UPDATE_UI_FUNCTION, payload: updates });
    } else {
      dispatch({ type: ActionTypes.UPDATE_UI, payload: updates });
    }
  }, []);

  const updateConnection = useCallback((updates) => {
    dispatch({ type: ActionTypes.UPDATE_CONNECTION, payload: updates });
  }, []);

  const updateCache = useCallback((updates) => {
    dispatch({ type: ActionTypes.UPDATE_CACHE, payload: updates });
  }, []);

  const updateSettings = useCallback((updates) => {
    dispatch({ type: ActionTypes.UPDATE_SETTINGS, payload: updates });
  }, []);

  const resetState = useCallback(() => {
    // Close existing EventSource connection before reset
    if (state.connection.eventSource) {
      state.connection.eventSource.close();
    }
    dispatch({ type: ActionTypes.RESET_STATE });
  }, [state.connection.eventSource]);

  // Get analysis settings for API request (mirrors original method)
  const getAnalysisSettings = useCallback(() => {
    return {
      username: state.settings.username,
      gameCount: state.settings.gameCount,
      gameTypes: state.settings.gameTypes,
      ratingFilter: state.settings.ratingFilter,
      gameResult: state.settings.gameResult,
      blunderThreshold: state.settings.blunderThreshold,
      analysisDepth: state.settings.analysisDepth
    };
  }, [state.settings]);

  // Validate current settings (mirrors original method)
  const validateSettings = useCallback(() => {
    const { username, gameTypes } = state.settings;
    return {
      isValid: username.length > 0 && gameTypes.length > 0,
      errors: {
        username: username.length === 0 ? 'Username is required' : null,
        gameTypes: gameTypes.length === 0 ? 'At least one game type must be selected' : null
      }
    };
  }, [state.settings]);

  // Context value
  const value = {
    // State
    ...state,
    
    // Actions
    updateAnalysis,
    updateUI,
    updateConnection,
    updateCache,
    updateSettings,
    resetState,
    
    // Utility methods
    getAnalysisSettings,
    validateSettings
  };

  return (
    <MCBContext.Provider value={value}>
      {children}
    </MCBContext.Provider>
  );
};

export default MCBContext; 