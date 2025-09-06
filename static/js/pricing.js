/**
 * Dynamic Pricing Frontend
 * Handles real-time prop pricing and order placement
 */

class PricingManager {
    constructor() {
        this.contracts = [];
        this.userOrders = [];
        this.currentUser = null;
        this.refreshInterval = null;
        this.init();
    }

    init() {
        this.loadContracts();
        this.setupEventListeners();
        this.startAutoRefresh();
    }

    async loadContracts() {
        try {
            const response = await fetch('/api/contracts');
            const data = await response.json();
            
            if (data.success) {
                this.contracts = data.contracts;
                this.renderContracts();
            } else {
                console.error('Failed to load contracts:', data.error);
            }
        } catch (error) {
            console.error('Error loading contracts:', error);
        }
    }

    async loadUserOrders(userId) {
        if (!userId) return;
        
        try {
            const response = await fetch(`/api/orders/user/${userId}`);
            const data = await response.json();
            
            if (data.success) {
                this.userOrders = data.orders;
                this.renderUserOrders();
            }
        } catch (error) {
            console.error('Error loading user orders:', error);
        }
    }

    renderContracts() {
        const container = document.getElementById('contracts-container');
        if (!container) return;

        container.innerHTML = '';

        // Group contracts by sport
        const nflContracts = this.contracts.filter(c => c.prop_id.startsWith('NFL_'));
        const mlbContracts = this.contracts.filter(c => c.prop_id.startsWith('MLB_'));

        // Render NFL contracts
        if (nflContracts.length > 0) {
            const nflSection = this.createSportSection('NFL', nflContracts);
            container.appendChild(nflSection);
        }

        // Render MLB contracts
        if (mlbContracts.length > 0) {
            const mlbSection = this.createSportSection('MLB', mlbContracts);
            container.appendChild(mlbSection);
        }
    }

    createSportSection(sport, contracts) {
        const section = document.createElement('div');
        section.className = 'sport-section';
        section.innerHTML = `
            <h2 class="sport-title">${sport} Props</h2>
            <div class="contracts-grid" id="${sport.toLowerCase()}-contracts">
            </div>
        `;

        const grid = section.querySelector('.contracts-grid');
        
        contracts.forEach(contract => {
            const contractCard = this.createContractCard(contract);
            grid.appendChild(contractCard);
        });

        return section;
    }

    createContractCard(contract) {
        const card = document.createElement('div');
        card.className = 'contract-card';
        card.innerHTML = `
            <div class="contract-header">
                <h3 class="player-name">${contract.player_name}</h3>
                <span class="prop-type">${this.formatPropType(contract.prop_type)}</span>
            </div>
            <div class="contract-details">
                <div class="prop-line">
                    <span class="line-label">Line:</span>
                    <span class="line-value">${contract.line}</span>
                </div>
                <div class="difficulty">
                    <span class="difficulty-badge ${contract.difficulty}">${contract.difficulty.toUpperCase()}</span>
                </div>
            </div>
            <div class="pricing-section">
                <div class="current-price">
                    <span class="price-label">Current Price:</span>
                    <span class="price-value">$${contract.current_price.toFixed(2)}</span>
                </div>
                <div class="volume">
                    <span class="volume-label">Volume:</span>
                    <span class="volume-value">${contract.total_volume}</span>
                </div>
            </div>
            <div class="order-section">
                <div class="order-inputs">
                    <input type="number" 
                           class="quantity-input" 
                           placeholder="Quantity" 
                           min="1" 
                           data-prop-id="${contract.prop_id}">
                    <input type="number" 
                           class="price-input" 
                           placeholder="Price" 
                           step="0.01" 
                           min="0.01" 
                           data-prop-id="${contract.prop_id}"
                           value="${contract.current_price.toFixed(2)}">
                </div>
                <div class="order-buttons">
                    <button class="buy-btn" data-prop-id="${contract.prop_id}">Buy</button>
                    <button class="sell-btn" data-prop-id="${contract.prop_id}">Sell</button>
                </div>
            </div>
        `;

        return card;
    }

    formatPropType(propType) {
        const typeMap = {
            'passing_yards': 'Passing Yards',
            'passing_tds': 'Passing TDs',
            'rushing_yards': 'Rushing Yards',
            'rushing_tds': 'Rushing TDs',
            'receiving_yards': 'Receiving Yards',
            'receiving_tds': 'Receiving TDs',
            'hits': 'Hits',
            'runs': 'Runs',
            'rbis': 'RBIs',
            'total_bases': 'Total Bases',
            'strikeouts': 'Strikeouts',
            'era': 'ERA',
            'pitches': 'Pitches'
        };
        return typeMap[propType] || propType;
    }

    renderUserOrders() {
        const container = document.getElementById('user-orders-container');
        if (!container) return;

        if (this.userOrders.length === 0) {
            container.innerHTML = '<p>No active orders</p>';
            return;
        }

        container.innerHTML = `
            <h3>Your Orders</h3>
            <div class="orders-list">
                ${this.userOrders.map(order => `
                    <div class="order-item">
                        <div class="order-details">
                            <span class="order-side ${order.side}">${order.side.toUpperCase()}</span>
                            <span class="order-quantity">${order.quantity} contracts</span>
                            <span class="order-price">$${order.price.toFixed(2)}</span>
                        </div>
                        <div class="order-actions">
                            <button class="cancel-order-btn" data-order-id="${order.order_id}">Cancel</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    setupEventListeners() {
        // Order placement
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('buy-btn')) {
                this.placeOrder(e.target.dataset.propId, 'buy');
            } else if (e.target.classList.contains('sell-btn')) {
                this.placeOrder(e.target.dataset.propId, 'sell');
            } else if (e.target.classList.contains('cancel-order-btn')) {
                this.cancelOrder(e.target.dataset.orderId);
            }
        });

        // Search functionality
        const searchInput = document.getElementById('contract-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchContracts(e.target.value);
            });
        }

        // Filter functionality
        const sportFilter = document.getElementById('sport-filter');
        if (sportFilter) {
            sportFilter.addEventListener('change', (e) => {
                this.filterContracts('sport', e.target.value);
            });
        }

        const difficultyFilter = document.getElementById('difficulty-filter');
        if (difficultyFilter) {
            difficultyFilter.addEventListener('change', (e) => {
                this.filterContracts('difficulty', e.target.value);
            });
        }
    }

    async placeOrder(propId, side) {
        if (!this.currentUser) {
            alert('Please log in to place orders');
            return;
        }

        const quantityInput = document.querySelector(`input[data-prop-id="${propId}"].quantity-input`);
        const priceInput = document.querySelector(`input[data-prop-id="${propId}"].price-input`);

        const quantity = parseInt(quantityInput.value);
        const price = parseFloat(priceInput.value);

        if (!quantity || quantity <= 0) {
            alert('Please enter a valid quantity');
            return;
        }

        if (!price || price <= 0) {
            alert('Please enter a valid price');
            return;
        }

        try {
            const response = await fetch('/api/orders', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: this.currentUser,
                    prop_id: propId,
                    side: side,
                    price: price,
                    quantity: quantity
                })
            });

            const data = await response.json();

            if (data.success) {
                alert(`Order placed successfully! Order ID: ${data.order_id}`);
                this.loadUserOrders(this.currentUser);
                this.loadContracts(); // Refresh to show updated prices
            } else {
                alert(`Error placing order: ${data.error}`);
            }
        } catch (error) {
            console.error('Error placing order:', error);
            alert('Error placing order. Please try again.');
        }
    }

    async cancelOrder(orderId) {
        try {
            const response = await fetch(`/api/orders/${orderId}/cancel`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success) {
                alert('Order cancelled successfully');
                this.loadUserOrders(this.currentUser);
                this.loadContracts(); // Refresh to show updated prices
            } else {
                alert(`Error cancelling order: ${data.error}`);
            }
        } catch (error) {
            console.error('Error cancelling order:', error);
            alert('Error cancelling order. Please try again.');
        }
    }

    searchContracts(query) {
        const cards = document.querySelectorAll('.contract-card');
        cards.forEach(card => {
            const playerName = card.querySelector('.player-name').textContent.toLowerCase();
            const propType = card.querySelector('.prop-type').textContent.toLowerCase();
            
            if (playerName.includes(query.toLowerCase()) || propType.includes(query.toLowerCase())) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }

    filterContracts(type, value) {
        const cards = document.querySelectorAll('.contract-card');
        cards.forEach(card => {
            if (value === '' || value === 'all') {
                card.style.display = 'block';
            } else {
                const propId = card.querySelector('[data-prop-id]').dataset.propId;
                const difficulty = card.querySelector('.difficulty-badge').textContent.toLowerCase();
                
                let show = true;
                
                if (type === 'sport') {
                    show = propId.startsWith(value.toUpperCase() + '_');
                } else if (type === 'difficulty') {
                    show = difficulty === value.toLowerCase();
                }
                
                card.style.display = show ? 'block' : 'none';
            }
        });
    }

    startAutoRefresh() {
        // Refresh contracts every 5 seconds to show updated prices
        this.refreshInterval = setInterval(() => {
            this.loadContracts();
            if (this.currentUser) {
                this.loadUserOrders(this.currentUser);
            }
        }, 5000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    setCurrentUser(userId) {
        this.currentUser = userId;
        this.loadUserOrders(userId);
    }
}

// Initialize pricing manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.pricingManager = new PricingManager();
});

// Export for use in other scripts
window.PricingManager = PricingManager;
