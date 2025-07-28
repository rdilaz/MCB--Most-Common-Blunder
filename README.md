# 🎯 MCB - Most Common Blunder

<div align="center">

![MCB Logo](mcb-react/public/logo.png)

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
- **Stockfish Engine**: Professional-grade analysis using the world's strongest chess engine
- **Batch Processing**: Analyze multiple games simultaneously for comprehensive insights

### 📊 **Detailed Blunder Breakdown**

- **Most Common Blunder**: Discover your #1 chess weakness
- **Categorized Analysis**: Blunders sorted by tactical, positional, endgame, and opening categories
- **Game-by-Game Breakdown**: See specific blunders in each analyzed game
- **Move-by-Move Analysis**: Understand exactly where and why blunders occurred

### ⚙️ **Customizable Analysis Settings**

- **Game Type Filtering**: Choose between blitz, rapid, bullet, or classical games
- **Rating Filters**: Analyze rated or unrated games
- **Result Filtering**: Focus on wins, losses, draws, or all games
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

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+
- A Chess.com account

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/MCB--Most-Common-Blunder.git
   cd MCB--Most-Common-Blunder
   ```

2. **Install Python dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies**

   ```bash
   cd mcb-react
   npm install
   ```

4. **Start the development servers**

   ```bash
   # In the mcb-react directory
   npm run dev:full
   ```

   This will start both the React frontend and Flask backend simultaneously.

5. **Open your browser**
   Navigate to `http://localhost:5173` to use the application.

## 📖 How to Use

1. **Enter Your Chess.com Username**: Input your Chess.com username in the analysis form
2. **Configure Settings**: Choose the number of games, game types, and analysis depth
3. **Start Analysis**: Click "Analyze Games" and wait for the real-time analysis to complete
4. **Review Results**: Explore your most common blunder, detailed breakdowns, and game-specific insights
5. **Improve Your Game**: Use the insights to focus your chess training on your biggest weaknesses

## 🎯 Example Analysis Results

- **Most Common Blunder**: "Hanging Pieces (32% of all blunders)"
- **Blunder Categories**: Tactical oversights, positional mistakes, endgame errors
- **Games Analyzed**: 50 recent blitz games
- **Total Blunders Found**: 127 across all games
- **Improvement Areas**: Pin tactics, back-rank threats, piece coordination

## 🏗️ Architecture

MCB uses a modular architecture designed for performance and scalability:

- **`app.py`** - Main Flask application with production-ready security
- **`analysis_service.py`** - Core chess analysis logic with parallel processing
- **`engines/stockfish_pool.py`** - Engine pool management for concurrent analysis
- **`mcb-react/src`** - Modern React frontend with component-based architecture

## 🤝 Contributing

We welcome contributions! Whether it's bug fixes, new features, or improvements to the analysis algorithms, your help makes MCB better for everyone.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Stockfish Team** - For the incredible chess engine that powers our analysis
- **Chess.com** - For providing the public API that enables game fetching
- **Python-Chess Library** - For excellent chess game processing capabilities

## 🐛 Issues & Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/your-username/MCB--Most-Common-Blunder/issues) page
2. Create a new issue with detailed information
3. Include your system info and steps to reproduce

---

<div align="center">

**Improve your chess, one blunder at a time!** ♟️

[Report Bug](https://github.com/your-username/MCB--Most-Common-Blunder/issues) • [Request Feature](https://github.com/your-username/MCB--Most-Common-Blunder/issues) • [Chess.com Profile](https://chess.com)

</div>
