# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCB (Most Common Blunder) is a chess analysis application that helps users identify and analyze their most common blunders. The project consists of a Flask backend and a React frontend with a modular architecture optimized for performance and scalability.

## Architecture

### Backend (Python/Flask)
- **app.py**: Main Flask application entry point with production-ready security features
- **routes.py**: Flask route definitions and application factory  
- **analysis_service.py**: Core chess game analysis logic with parallel processing capabilities
- **analyze_games.py**: **PRIMARY PERFORMANCE BOTTLENECK** - Contains heavy engine analysis logic
- **config.py**: Centralized configuration with production settings
- **utils.py**: Utility functions for data processing and validation
- **progress_tracking.py**: Real-time progress tracking for analysis operations
- **engines/stockfish_pool.py**: Engine pool management for concurrent analysis
- **get_games.py**: Chess.com API integration with concurrent fetching
- **performance_monitor.py**: Performance metrics and monitoring

### Frontend (React)
- **mcb-react/**: React application built with Vite
- **src/context/MCBContext.jsx**: Centralized state management using React Context
- **src/hooks/useAnalysis.js**: Custom hook for analysis operations
- **src/components/**: Modular UI components organized by type (forms, results, ui)
  - **results/GamesSection.jsx**: Games with blunders display (recently fixed UI bug)
  - **results/GameBlunderItem.jsx**: Individual game blunder display with scrollable containers
- **src/styles/main.css**: Chess-themed styling with responsive design

### Key Dependencies
- Backend: Flask, chess library, Stockfish engine, Flask-CORS, Flask-Limiter, concurrent.futures
- Frontend: React 19, Vite, modern ES6+ features

## Common Development Commands

### Backend Development
```bash
# Start Flask development server
python app.py

# Install Python dependencies
pip install -r requirements.txt
```

### Frontend Development
```bash
# Navigate to React app
cd mcb-react

# Install dependencies
npm install

# Start development server
npm run dev

# Start both frontend and backend
npm run dev:full

# Build for production
npm run build

# Lint code
npm run lint
```

## Key Technical Details

### State Management
The application uses React Context (MCBContext) for state management with the following main state sections:
- **analysis**: Current analysis session state
- **ui**: UI state (progress, visibility)
- **connection**: WebSocket/EventSource connections
- **cache**: Data caching for games and blunders
- **settings**: User configuration (username, game types, analysis depth)

### Analysis Pipeline
1. User submits analysis request through AnalysisForm
2. Backend fetches games from chess.com API
3. Stockfish analyzes games for blunders using optimized engine settings
4. Real-time progress updates via Server-Sent Events
5. Results displayed in modular components (BlundersSection, GamesSection)

### Performance Analysis & Optimizations

#### Primary Performance Bottleneck: analyze_games.py
**analyze_games.py** is the most computationally intensive file in the codebase:
- **Engine Call Intensity**: Makes 1-2 Stockfish engine calls per move (0.05-0.15s each)
- **Move-by-Move Processing**: Processes every move in every game sequentially  
- **Heavy Functions**: `categorize_blunder()` runs 11+ detection algorithms, `see()` performs recursive analysis
- **Nested Complexity**: Each move triggers board copying, tactical pattern checks, and position analysis

#### Current Optimizations (Implemented)
- **Stockfish Engine Pool**: Configurable pool size with lazy initialization and connection reuse
- **Async API Calls**: Concurrent chess.com API fetching with 79.5% performance improvement
- **Single-pass PGN Processing**: Eliminated double-pass processing, reduced memory usage by 70%
- **Analysis Speed**: 3 depth levels (fast: 0.05s, balanced: 0.08s, deep: 0.15s per move)
- **Smart Move Filtering**: Enhanced heuristics reduce engine calls from 2 to ~1.4 per move
- **Parallel Processing**: ThreadPoolExecutor implementation for 200+ game analysis
- **Rate Limiting**: Production-ready limits (5 requests/minute, 200 games/day per user)
- **Dynamic Think Times**: Position complexity-based engine time allocation

#### Performance Characteristics
- **Current Capacity**: Efficiently handles 1-50 games (~2-10 minutes)
- **Large Scale**: 200+ games use parallel processing (~15-25 minutes)
- **Memory Usage**: ~1 game worth of data in memory at a time (optimized)
- **Engine Pool**: Configurable size (default 2-5 engines based on workload)

#### Optimization Opportunities in analyze_games.py
1. **Parallel Move Processing**: Currently sequential move analysis within games
2. **Enhanced Caching**: Board evaluations and tactical patterns could be cached
3. **Early Termination**: Skip analysis in completely decided positions sooner
4. **Algorithm Optimization**: Reduce complexity in blunder detection functions

### Security Features
- Flask-Limiter for rate limiting
- Input validation and sanitization
- CORS configuration
- Session management with daily limits

## File Structure Highlights

```
├── app.py                          # Main application entry
├── routes.py                       # Flask routes
├── analysis_service.py             # Core analysis orchestration
├── analyze_games.py               # PRIMARY BOTTLENECK - Heavy engine analysis
├── config.py                       # Configuration
├── get_games.py                    # Chess.com API integration
├── performance_monitor.py          # Performance tracking
├── progress_tracking.py            # Real-time progress updates
├── utils.py                        # Utility functions
├── engines/
│   └── stockfish_pool.py          # Engine pool management
├── stockfish/                      # Stockfish engine binaries
├── mcb-react/                      # React frontend
│   ├── src/
│   │   ├── context/MCBContext.jsx  # State management
│   │   ├── hooks/useAnalysis.js    # Analysis operations
│   │   ├── components/
│   │   │   ├── forms/AnalysisForm.jsx
│   │   │   ├── results/
│   │   │   │   ├── GamesSection.jsx      # Games display (fixed UI bug)
│   │   │   │   ├── GameBlunderItem.jsx   # Scrollable blunder cards
│   │   │   │   └── BlundersSection.jsx
│   │   │   └── ui/
│   │   └── styles/main.css         # Chess-themed responsive styling
│   └── package.json
└── requirements.txt                # Python dependencies
```

## Development Workflow

1. **Backend Changes**: Modify Python files and restart `python app.py`
2. **Frontend Changes**: React dev server auto-reloads via `npm run dev`
3. **Full Stack**: Use `npm run dev:full` to run both simultaneously
4. **Testing**: Backend handles integration testing, frontend uses React dev tools

## Recent Fixes & Improvements

### UI Fixes
- **Fixed Blunder Card Cutoff Bug (2024)**: Games with many blunders (9+) had cards cut off in "Show blunders" menu
  - **Root Cause**: Fixed `max-height: 800px` in `.game-blunder-details:not(.collapsed)` 
  - **Solution**: Implemented responsive scrollable containers with `max-height: 60vh` and `overflow-y: auto`
  - **Features**: Custom scrollbar styling, responsive breakpoints for different screen sizes
  - **Files Modified**: `mcb-react/src/styles/main.css:1417-1465`

### Performance Optimizations
- **Parallel Processing**: Implemented for 200+ game analysis
- **Enhanced Heuristics**: Reduced unnecessary engine calls by 30%
- **Engine Pool Management**: Dynamic scaling based on workload

## Important Technical Notes

### Performance Considerations
- **analyze_games.py** is the primary performance bottleneck - focus optimization efforts here
- Engine pool size can be configured in `config.py` (ENGINE_POOL_SIZE)
- Parallel processing automatically activates for 20+ games
- Use performance monitoring to track engine utilization and processing times

### UI/UX Best Practices
- All blunder displays should use scrollable containers to prevent cutoff
- Responsive design targets full-screen, half-screen, and mobile viewports
- Dark chess theme with custom scrollbars for consistency
- Real-time progress updates are critical for user experience during analysis

### Security & Production
- Rate limiting is enforced (5 requests/minute, 200 games/day per user)
- Input validation on all user inputs
- Engine pool prevents resource exhaustion
- Comprehensive error handling and logging throughout

### Development Environment
- The Stockfish engine is included in the `stockfish/` directory
- Production configuration is environment-aware (dev vs production modes)
- Error handling is comprehensive with proper logging throughout
- The codebase follows modular architecture patterns for maintainability