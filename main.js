// Wait for DOM to be loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const analysisForm = document.getElementById('analysis-form');
    const usernameInput = document.getElementById('username-input');
    const loadingSection = document.getElementById('loading-section');
    const errorSection = document.getElementById('error-section');
    const errorMessage = document.getElementById('error-message');
    const resultsSection = document.getElementById('results-section');
    const toggleBlundersBtn = document.getElementById('toggle-blunders-btn');
    const blundersContainer = document.getElementById('blunders-container');

    // State management
    let isBlundersVisible = false;

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

    // Main analysis function
    async function analyzePlayer(username) {
        showLoading();
        hideError();
        hideResults();

        try {
            const response = await fetch(`/api/analyze/${username}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Analysis failed');
            }

            displayResults(data);
            
        } catch (error) {
            console.error('Analysis error:', error);
            showError(error.message || 'Failed to analyze games. Please try again.');
        } finally {
            hideLoading();
        }
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
        document.getElementById('most-common-example').textContent = mostCommon.example;
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
        document.querySelector('.category-breakdown').style.display = 'block';
        document.querySelector('.toggle-section').style.display = 'block';
    }

    // Helper function to capitalize first letter
    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    // Auto-focus on username input
    usernameInput.focus();
});
