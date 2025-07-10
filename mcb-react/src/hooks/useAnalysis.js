import { useCallback } from 'react';
import { useMCB } from '../context/MCBContext';

// Custom hook for analysis operations (mirrors AnalysisController)
export const useAnalysis = () => {
  const { 
    analysis, 
    connection,
    updateAnalysis, 
    updateConnection, 
    updateUI,
    updateCache,
    getAnalysisSettings, 
    validateSettings 
  } = useMCB();

  // Generate session ID (mirrors original method)
  const generateSessionId = useCallback(() => {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
  }, []);

  // Start analysis (mirrors AnalysisController.startAnalysis)
  const startAnalysis = useCallback(async () => {
    if (analysis.isAnalyzing) return;
    
    const validation = validateSettings();
    if (!validation.isValid) {
      const errorMessage = Object.values(validation.errors).filter(error => error).join('\n');
      alert(errorMessage);
      return;
    }
    
    try {
      // Generate session ID and update state
      const sessionId = generateSessionId();
      updateAnalysis({
        sessionId: sessionId,
        isAnalyzing: true,
        currentSettings: getAnalysisSettings()
      });
      
      // Update UI state
      updateUI({
        progressVisible: true,
        resultsVisible: false,
        currentProgress: 0,
        progressLogs: []
      });
      
      // Start progress tracking FIRST (like original)
      startProgressTracking(sessionId);
      
      // Send analysis request to Flask backend
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          ...getAnalysisSettings()
        })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('Analysis started:', data);
      
    } catch (error) {
      console.error('Analysis failed:', error);
      handleAnalysisError(error.message);
    }
  }, [analysis.isAnalyzing, validateSettings, generateSessionId, updateAnalysis, updateUI, getAnalysisSettings]);

  // Start progress tracking via Server-Sent Events (mirrors original)
  const startProgressTracking = useCallback((sessionId) => {
    // Close existing connection
    if (connection.eventSource) {
      connection.eventSource.close();
    }
    
    const eventSource = new EventSource(`/api/progress/${sessionId}`);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleProgressUpdate(data);
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
    
    updateConnection({
      eventSource: eventSource,
      isConnected: true
    });
  }, [connection.eventSource, updateConnection]);

  // Handle progress updates (mirrors original)
  const handleProgressUpdate = useCallback((data) => {
    console.log('Progress update:', data);
    
    // Handle heartbeat
    if (data.heartbeat) {
      updateConnection({ lastHeartbeat: Date.now() });
      return;
    }
    
    // Update progress bar
    if (data.percentage !== undefined) {
      updateUI({ currentProgress: data.percentage });
    }
    
    // Add progress log entry - FIXED to properly add new entries
    if (data.message) {
      updateUI(prevState => ({
        ...prevState,
        progressLogs: [...(prevState.progressLogs || []), {
          message: data.message,
          timestamp: new Date().toLocaleTimeString()
        }]
      }));
    }
    
    // Handle completion
    if (data.status === 'completed' && data.results) {
      handleAnalysisComplete(data.results);
    } else if (data.status === 'error') {
      handleAnalysisError(data.error || 'Unknown error occurred');
    }
  }, [updateConnection, updateUI]);

  // Handle analysis completion (mirrors original)
  const handleAnalysisComplete = useCallback((results) => {
    console.log('Analysis completed:', results);
    
    updateAnalysis({
      isAnalyzing: false,
      results: results
    });
    
    // Close progress tracking
    if (connection.eventSource) {
      connection.eventSource.close();
      updateConnection({
        eventSource: null,
        isConnected: false
      });
    }
    
    // Update progress to 100%
    updateUI({ currentProgress: 100 });
    
    // Add final completion log message (was missing!)
    updateUI(prevState => ({
      ...prevState,
      progressLogs: [...(prevState.progressLogs || []), {
        message: '✅ Analysis completed!',
        timestamp: new Date().toLocaleTimeString()
      }]
    }));
    
    // Cache results
    updateCache({
      gamesWithBlunders: results.games_with_blunders || [],
      blunderData: results.blunder_breakdown || [],
      heroStat: results.hero_stat
    });
    
    // Set global variable for backward compatibility (was missing!)
    window.gamesWithBlunders = results.games_with_blunders || [];
    
    // Show results after a brief delay
    setTimeout(() => {
      updateUI({ resultsVisible: true });
    }, 1000);
  }, [updateAnalysis, connection.eventSource, updateConnection, updateUI, updateCache]);

  // Handle analysis errors (mirrors original)
  const handleAnalysisError = useCallback((errorMessage) => {
    console.error('Analysis error:', errorMessage);
    
    updateAnalysis({ isAnalyzing: false });
    
    if (connection.eventSource) {
      connection.eventSource.close();
      updateConnection({
        eventSource: null,
        isConnected: false
      });
    }
    
    // Add error log message (was missing!)
    updateUI(prevState => ({
      ...prevState,
      progressLogs: [...(prevState.progressLogs || []), {
        message: `❌ Error: ${errorMessage}`,
        timestamp: new Date().toLocaleTimeString()
      }]
    }));
    
    alert(`Analysis failed: ${errorMessage}`);
  }, [updateAnalysis, connection.eventSource, updateConnection, updateUI]);

  return {
    // State
    isAnalyzing: analysis.isAnalyzing,
    sessionId: analysis.sessionId,
    results: analysis.results,
    
    // Actions
    startAnalysis,
    handleAnalysisError
  };
};

export default useAnalysis; 