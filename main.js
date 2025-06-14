// Wait for the DOM to be loaded before executing the script
document.addEventListener('DOMContentLoaded', function() {
    // 1. Get elements
    // 1.1 Get the button element
    const toggleBlundersBtn = document.getElementById('toggle-blunders-btn');
    // 1.2 Get the blunder cards
    const blunderCards = document.querySelectorAll('.blunder-card');
    // 2. Add event listener for clicks
    // this functions runs when the button is clicked
    toggleBlundersBtn.addEventListener('click', function() {
        // loop through all blunder cards found at step 1.2
        blunderCards.forEach(function(card) {
            // check the display style of the card
            // if visible (not "none"), hide it
            if (card.style.display !== 'none') {
                card.style.display = 'none';
            } else {
                // otherwise, show it
                card.style.display = 'block';
            }
        });
    });
});
