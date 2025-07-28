# 🎯 MCB - Most Common Blunder

<div align="center">

<img src="mcb-react/public/logo.png" alt="MCB Logo" width="120" height="120">

**Discover your chess weaknesses and improve your game**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-19.1+-61DAFB.svg)](https://reactjs.org/)
[![Flask](https://img.shields.io/badge/Flask-Latest-green.svg)](https://flask.palletsprojects.com/)
[![Stockfish](https://img.shields.io/badge/Engine-Stockfish-red.svg)](https://stockfishchess.org/)

</div>

## 🚀 What is MCB?

MCB (Most Common Blunder) is a powerful chess analysis tool that helps players identify their most frequent mistakes and improve their game. By analyzing your Chess.com games with the Stockfish engine, MCB provides detailed insights into your blunders, categorizes them by type, and shows you exactly where you need to focus your training.

## ✨ Features

### 🔍 **Comprehensive Game Analysis**

- **Chess.com Integration**: Automatically fetch and analyze games from your Chess.com profile
- **Stockfish 16 Engine**: Professional-grade analysis using the world's strongest chess engine
- **Batch Processing**: Analyze multiple games simultaneously (up to 200 games)

### 📊 **Detailed Blunder Breakdown**

- **Most Common Blunder**: Discover your #1 chess weakness
- **Game-by-Game Breakdown**: See specific blunders in each analyzed game
- **Move-by-Move Analysis**: Understand exactly where and why blunders occurred

### ⚙️ **Customizable Analysis Settings**

- **Game Type Filtering**: Choose between blitz, rapid, bullet, or classical games
- **Rating Filters**: Analyze rated or unrated games
- **Result Filtering**: Focus on wins, losses, or both
- **Adjustable Thresholds**: Customize what constitutes a "blunder" (centipawn loss)
- **Analysis Depth**: Choose between fast analysis or deep evaluation

### 🎮 **User-Friendly Interface**

- **Real-time Progress**: Live updates during analysis with detailed logs
- **Modern UI**: Clean, responsive design that works on all devices
- **Developer Mode**: Direct PGN input for testing and custom analysis
- **Interactive Results**: Click through games and blunders with ease

## 🛠️ Tech Stack

**Backend:**

- **Flask** - Web framework
- **Python-Chess** - Chess game logic and PGN processing
- **Stockfish** - Chess engine for analysis
- **Requests** - Chess.com API integration

**Frontend:**

- **React 19** - Modern UI framework
- **Vite** - Fast build tool and development server
- **Context API** - State management
- **CSS3** - Custom responsive styling

## 🚀 Try It Live

<div align="center">

**Ready to discover your chess blunders?**

[![Launch MCB](https://img.shields.io/badge/🎯_Launch_MCB-Live_App-blue?style=for-the-badge&logoColor=white)](https://your-app-url-here.com)

_Just enter your Chess.com username and start analyzing!_

</div>

## 📖 How to Use

1. **Enter Your Chess.com Username**: Input your Chess.com username in the analysis form
2. **Configure Settings**: Choose the number of games, game types, and analysis depth
3. **Start Analysis**: Click "Analyze Games" and wait for the real-time analysis to complete
4. **Review Results**: Explore your most common blunder, detailed breakdowns, and game-specific insights
5. **Improve Your Game**: Use the insights to focus your chess training on your biggest weaknesses

## 🏗️ Architecture

MCB uses a modular architecture designed for performance and scalability:

- **`app.py`** - Main Flask application with production-ready security
- **`analysis_service.py`** - Core chess analysis logic with parallel processing
- **`engines/stockfish_pool.py`** - Engine pool management for concurrent analysis
- **`mcb-react/src`** - Modern React frontend with component-based architecture

## 🙏 Acknowledgments

- **Stockfish Team** - For the incredible chess engine that powers our analysis
- **Chess.com** - For providing the public API that enables game fetching
- **Python-Chess Library** - For excellent chess game processing capabilities

---

<div align="center">

**Improve your chess, one blunder at a time!** ♟️

</div>
