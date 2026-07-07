// Flight utilities for domestic/international detection and airline assignment

// Kenyan airports (domestic)
const KENYAN_AIRPORTS = [
    'NBO', // Nairobi - Jomo Kenyatta International
    'MBA', // Mombasa - Moi International
    'KIS', // Kisumu - Kisumu International
    'EDL', // Eldoret - Eldoret International
    'WIL'  // Nairobi - Wilson Airport
];

// Regional airports (East Africa)
const REGIONAL_AIRPORTS = [
    'EBB', // Entebbe, Uganda
    'JRO', // Kilimanjaro, Tanzania
    'DAR', // Dar es Salaam, Tanzania
    'KGL', // Kigali, Rwanda
    'MPM'  // Maputo, Mozambique
];

/**
 * Determine if a route is domestic (both airports in Kenya)
 * @param {string} from - Origin airport code
 * @param {string} to - Destination airport code
 * @returns {boolean} - True if domestic route
 */
function isDomesticRoute(from, to) {
    return KENYAN_AIRPORTS.includes(from) && KENYAN_AIRPORTS.includes(to);
}

/**
 * Determine if a route is regional (East Africa)
 * @param {string} from - Origin airport code
 * @param {string} to - Destination airport code
 * @returns {boolean} - True if regional route
 */
function isRegionalRoute(from, to) {
    return (KENYAN_AIRPORTS.includes(from) && REGIONAL_AIRPORTS.includes(to)) ||
           (REGIONAL_AIRPORTS.includes(from) && KENYAN_AIRPORTS.includes(to)) ||
           (REGIONAL_AIRPORTS.includes(from) && REGIONAL_AIRPORTS.includes(to));
}

/**
 * Get route category
 * @param {string} from - Origin airport code
 * @param {string} to - Destination airport code
 * @returns {string} - Route category: 'domestic', 'regional', or 'international'
 */
function getRouteCategory(from, to) {
    if (isDomesticRoute(from, to)) return 'domestic';
    if (isRegionalRoute(from, to)) return 'regional';
    return 'international';
}

/**
 * Get appropriate airlines for a route based on category
 * @param {string} from - Origin airport code
 * @param {string} to - Destination airport code
 * @returns {Array} - Array of airline objects
 */
function getAirlinesForRoute(from, to) {
    const category = getRouteCategory(from, to);
    
    const domesticAirlines = [
        { name: 'Kenya Airways', code: 'KQ', logo: '✈️', probability: 0.4 },
        { name: 'JamboJet', code: 'JM', logo: '✈️', probability: 0.25 },
        { name: 'SmartFly', code: 'SF', logo: '✈️', probability: 0.2 },
        { name: 'RwandAir', code: 'WB', logo: '✈️', probability: 0.1 },
        { name: 'Ethiopian Airlines', code: 'ET', logo: '✈️', probability: 0.05 }
    ];
    
    const regionalAirlines = [
        { name: 'Kenya Airways', code: 'KQ', logo: '✈️', probability: 0.35 },
        { name: 'Ethiopian Airlines', code: 'ET', logo: '✈️', probability: 0.25 },
        { name: 'RwandAir', code: 'WB', logo: '✈️', probability: 0.2 },
        { name: 'Qatar Airways', code: 'QR', logo: '🛬', probability: 0.1 },
        { name: 'Emirates', code: 'EK', logo: '✈️', probability: 0.1 }
    ];
    
    const internationalAirlines = [
        { name: 'Kenya Airways', code: 'KQ', logo: '✈️', probability: 0.2 },
        { name: 'Qatar Airways', code: 'QR', logo: '🛬', probability: 0.2 },
        { name: 'Emirates', code: 'EK', logo: '✈️', probability: 0.2 },
        { name: 'British Airways', code: 'BA', logo: '🛫', probability: 0.15 },
        { name: 'Ethiopian Airlines', code: 'ET', logo: '✈️', probability: 0.15 },
        { name: 'RwandAir', code: 'WB', logo: '✈️', probability: 0.1 }
    ];
    
    switch(category) {
        case 'domestic':
            return domesticAirlines;
        case 'regional':
            return regionalAirlines;
        case 'international':
            return internationalAirlines;
        default:
            return internationalAirlines;
    }
}

/**
 * Select an airline based on probability weights
 * @param {Array} airlines - Array of airline objects with probability
 * @returns {Object} - Selected airline
 */
function selectAirlineByProbability(airlines) {
    const random = Math.random();
    let cumulativeProbability = 0;
    
    for (const airline of airlines) {
        cumulativeProbability += airline.probability;
        if (random <= cumulativeProbability) {
            return airline;
        }
    }
    
    // Fallback to first airline
    return airlines[0];
}

/**
 * Get applicable offers for a route and airline
 * @param {string} from - Origin airport code
 * @param {string} to - Destination airport code
 * @param {string} airline - Airline name
 * @param {string} travelDate - Travel date (YYYY-MM-DD)
 * @returns {Array} - Array of applicable offers
 */
async function getApplicableOffers(from, to, airline, travelDate) {
    try {
        const response = await fetch('/assets/data/airline-offers.json');
        const data = await response.json();
        const offers = data.offers || [];
        const routeKey = `${from}-${to}`;
        const category = getRouteCategory(from, to);
        
        return offers.filter(offer => {
            // Check if offer is active
            if (!offer.active) return false;
            
            // Check if airline matches
            if (offer.airline !== airline) return false;
            
            // Check date validity
            const travelDateObj = new Date(travelDate);
            const validFrom = new Date(offer.validFrom);
            const validTo = new Date(offer.validTo);
            
            if (travelDateObj < validFrom || travelDateObj > validTo) return false;
            
            // Check route applicability
            if (offer.routes.includes('domestic') && category !== 'domestic') return false;
            if (offer.routes.includes('international') && category !== 'international') return false;
            if (offer.routes.includes('regional') && category !== 'regional') return false;
            
            // Check specific routes
            const hasSpecificRoutes = offer.routes.some(route => route.includes('-'));
            if (hasSpecificRoutes && !offer.routes.includes(routeKey)) return false;
            
            return true;
        });
    } catch (error) {
        console.error('Error loading offers:', error);
        return [];
    }
}

/**
 * Get all active offers for display on dashboard
 * @returns {Array} - Array of active offers
 */
async function getAllActiveOffers() {
    try {
        const response = await fetch('/assets/data/airline-offers.json');
        const data = await response.json();
        const offers = data.offers || [];
        const now = new Date();
        
        return offers.filter(offer => {
            if (!offer.active) return false;
            
            const validFrom = new Date(offer.validFrom);
            const validTo = new Date(offer.validTo);
            
            return now >= validFrom && now <= validTo;
        }).sort((a, b) => {
            // Sort by priority (lower number = higher priority)
            if (a.priority !== b.priority) {
                return a.priority - b.priority;
            }
            // Then by validity end date (soonest expiring first)
            return new Date(a.validTo) - new Date(b.validTo);
        });
    } catch (error) {
        console.error('Error loading offers:', error);
        return [];
    }
}

/**
 * Calculate time remaining until offer expires
 * @param {string} validTo - Valid until date (YYYY-MM-DD)
 * @returns {Object} - Object with days, hours, minutes, seconds
 */
function getTimeRemaining(validTo) {
    const total = Date.parse(validTo) - Date.parse(new Date());
    const seconds = Math.floor((total / 1000) % 60);
    const minutes = Math.floor((total / 1000 / 60) % 60);
    const hours = Math.floor((total / (1000 * 60 * 60)) % 24);
    const days = Math.floor(total / (1000 * 60 * 60 * 24));
    
    return { total, days, hours, minutes, seconds };
}

/**
 * Format price with currency
 * @param {number} price - Price amount
 * @param {string} currency - Currency code (default: KES)
 * @returns {string} - Formatted price string
 */
function formatPrice(price, currency = 'KES') {
    if (currency === 'KES') {
        return `Ksh ${price.toLocaleString()}`;
    }
    return `${price.toLocaleString()} ${currency}`;
}

/**
 * Apply offer discount to price
 * @param {number} basePrice - Original price
 * @param {Object} offer - Offer object
 * @returns {number} - Discounted price
 */
function applyOfferDiscount(basePrice, offer) {
    if (!offer || !offer.discount) return basePrice;
    
    const discountAmount = basePrice * (offer.discount / 100);
    return Math.round(basePrice - discountAmount);
}

// Export functions for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        isDomesticRoute,
        isRegionalRoute,
        getRouteCategory,
        getAirlinesForRoute,
        selectAirlineByProbability,
        getApplicableOffers,
        getAllActiveOffers,
        getTimeRemaining,
        formatPrice,
        applyOfferDiscount
    };
}