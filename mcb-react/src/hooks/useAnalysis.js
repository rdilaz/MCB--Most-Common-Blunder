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
        currentSettings: getAnalysisSettings(),
        startTime: Date.now()
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

  // Start progress tracking via simple polling (much more reliable than EventSource)
  const startProgressTracking = useCallback((sessionId) => {
    console.log('Starting progress tracking with polling');
    
    // Close any existing EventSource
    if (connection.eventSource) {
      connection.eventSource.close();
    }
    
    // Use polling instead of EventSource
    const pollProgress = async () => {
      try {
        const response = await fetch(`/api/status/${sessionId}`);
        if (!response.ok) throw new Error('Status check failed');
        
                 const data = await response.json();
         console.log('Progress poll:', data);
         
         // Handle progress update inline
         if (data.percentage !== undefined) {
           updateUI({ currentProgress: data.percentage });
         }
         
         if (data.message) {
           updateUI(prevState => ({
             ...prevState,
             progressLogs: [...(prevState.progressLogs || []), {
               message: data.message,
               timestamp: new Date().toLocaleTimeString(),
               rawTimestamp: Date.now()
             }]
           }));
         }
         
         // Handle completion
         if (data.status === 'completed' && data.results) {
           updateAnalysis({ isAnalyzing: false, results: data.results });
           updateUI({ resultsVisible: true, progressVisible: false });
         } else if (data.status === 'error') {
           updateAnalysis({ isAnalyzing: false });
           updateUI({ progressVisible: false });
           alert(`Analysis failed: ${data.error || 'Unknown error'}`);
         }
        
        // Continue polling if analysis is still running
        if (analysis.isAnalyzing && data.status !== 'completed' && data.status !== 'error') {
          setTimeout(pollProgress, 2000); // Poll every 2 seconds
        }
      } catch (error) {
        console.error('Progress polling error:', error);
        if (analysis.isAnalyzing) {
          setTimeout(pollProgress, 3000); // Retry in 3 seconds
        }
      }
    };
    
    // Start polling
    pollProgress();
    
    updateConnection({ isConnected: true });
  }, [updateConnection, analysis.isAnalyzing, updateUI, updateAnalysis]);

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
          timestamp: new Date().toLocaleTimeString(),
          rawTimestamp: Date.now()
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
        timestamp: new Date().toLocaleTimeString(),
        rawTimestamp: Date.now()
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