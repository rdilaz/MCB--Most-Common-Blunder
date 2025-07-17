# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCB (Most Common Blunder) is a chess analysis application that helps users identify and analyze their most common blunders. The project consists of a Flask backend and a React frontend with a modular architecture.

## Architecture

### Backend (Python/Flask)
- **app.py**: Main Flask application entry point with production-ready security features
- **routes.py**: Flask route definitions and application factory
- **analysis_service.py**: Core chess game analysis logic using Stockfish engine
- **config.py**: Centralized configuration with production settings
- **utils.py**: Utility functions for data processing and validation
- **progress_tracking.py**: Real-time progress tracking for analysis operations

### Frontend (React)
- **mcb-react/**: React application built with Vite
- **src/context/MCBContext.jsx**: Centralized state management using React Context
- **src/hooks/useAnalysis.js**: Custom hook for analysis operations
- **src/components/**: Modular UI components organized by type (forms, results, ui)

### Key Dependencies
- Backend: Flask, chess library, Stockfish engine, Flask-CORS, Flask-Limiter
- Frontend: React 19, Vite, Stagewise (AI-powered UI editing in development)

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

### Performance Optimizations

#### Current Optimizations (Implemented)
- **Stockfish Engine Pool**: 2-engine pool with lazy initialization and connection reuse
- **Async API Calls**: Concurrent chess.com API fetching with 79.5% performance improvement
- **Single-pass PGN Processing**: Eliminated double-pass processing, reduced memory usage by 70%
- **Analysis Speed**: 3 depth levels (fast: 0.05s, balanced: 0.08s, deep: 0.15s per move)
- **Smart Move Filtering**: Heuristic-based filtering reduces engine calls from 2 to ~1.4 per move
- **Rate Limiting**: Production-ready limits (5 requests/minute, 200 games/day per user)
- **Concurrent Session Management**: Max 10 active users

#### Performance Characteristics
- **Current Capacity**: Efficiently handles 1-50 games (~2-10 minutes)
- **Scaling Challenge**: 200+ games currently require ~35 minutes due to sequential processing
- **Memory Usage**: ~1 game worth of data in memory at a time (optimized)
- **Engine Utilization**: 33% (2 engines used sporadically)

#### Identified Bottlenecks for Large-Scale Analysis
1. **Sequential Game Analysis**: Primary bottleneck preventing 200+ game efficiency
2. **Engine Pool Underutilization**: Only 2 engines used when more could be beneficial
3. **Move-by-Move Sequential Processing**: Each game analyzed sequentially

#### Proposed High-Priority Optimizations
- **Parallel Game Analysis**: 4x speedup potential with ThreadPoolExecutor
- **Engine Pool Scaling**: Increase from 2 to 6 engines for better utilization
- **Memory Streaming**: Direct-to-file blunder writing for 70% memory reduction
- **Enhanced Heuristics**: Additional 25% reduction in engine calls

### Security Features
- Flask-Limiter for rate limiting
- Input validation and sanitization
- CORS configuration
- Session management with daily limits

## File Structure Highlights

```
├── app.py                          # Main application entry
├── routes.py                       # Flask routes
├── analysis_service.py             # Core analysis logic
├── config.py                       # Configuration
├── stockfish/                      # Stockfish engine
├── mcb-react/                      # React frontend
│   ├── src/
│   │   ├── context/MCBContext.jsx  # State management
│   │   ├── hooks/useAnalysis.js    # Analysis operations
│   │   ├── components/             # UI components
│   │   └── styles/main.css         # Styling
│   └── package.json
└── requirements.txt                # Python dependencies
```

## Development Workflow

1. **Backend Changes**: Modify Python files and restart `python app.py`
2. **Frontend Changes**: React dev server auto-reloads via `npm run dev`
3. **Full Stack**: Use `npm run dev:full` to run both simultaneously
4. **Testing**: Backend handles integration testing, frontend uses React dev tools

## Important Notes

- The Stockfish engine is included in the `stockfish/` directory
- Production configuration is environment-aware (dev vs production modes)
- The React app uses Stagewise for AI-powered UI editing in development
- Error handling is comprehensive with proper logging throughout
- The codebase follows modular architecture patterns for maintainability