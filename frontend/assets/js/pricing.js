/**
 * Dynamic Flight Pricing System
 * Calculates fares based on distance using Haversine formula
 */

// Pricing configuration
const PRICING_CONFIG = {
    pricePerKm: 0.12,           // Base price per kilometer (USD)
    minimumFare: 50,            // Minimum fare for any flight (USD)
    
    // Fare class multipliers
    fareClasses: {
        standard: {
            name: 'Standard',
            multiplier: 1.0,
            description: 'Basic fare with standard flexibility'
        },
        flex: {
            name: 'Flex',
            multiplier: 1.35,
            description: 'Change flights with reduced fees'
        },
        superflex: {
            name: 'Super Flex',
            multiplier: 1.75,
            description: 'Full flexibility with free changes'
        }
    },
    
    // Additional pricing factors
    surcharges: {
        peak: 1.15,             // Peak season/time multiplier
        weekend: 1.08,          // Weekend flight multiplier
        holiday: 1.25           // Holiday period multiplier
    }
};

/**
 * Calculate distance between two points using Haversine formula
 * @param {number} lat1 - Latitude of first point
 * @param {number} lon1 - Longitude of first point
 * @param {number} lat2 - Latitude of second point
 * @param {number} lon2 - Longitude of second point
 * @returns {number} Distance in kilometers
 */
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in kilometers
    
    // Convert degrees to radians
    const toRad = (deg) => deg * (Math.PI / 180);
    
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    
    const a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distance = R * c;
    
    return Math.round(distance); // Round to nearest km
}

/**
 * Calculate base fare from distance
 * @param {number} distanceKm - Distance in kilometers
 * @returns {number} Base fare in USD
 */
function calculateBaseFare(distanceKm) {
    const fare = distanceKm * PRICING_CONFIG.pricePerKm;
    return Math.max(fare, PRICING_CONFIG.minimumFare);
}

/**
 * Apply fare class multiplier
 * @param {number} baseFare - Base fare amount
 * @param {string} fareClass - Fare class key ('standard', 'flex', 'superflex')
 * @returns {number} Final fare with multiplier applied
 */
function applyFareClass(baseFare, fareClass = 'standard') {
    const classConfig = PRICING_CONFIG.fareClasses[fareClass];
    if (!classConfig) return baseFare;
    
    return baseFare * classConfig.multiplier;
}

/**
 * Calculate flight price between two airports
 * @param {Object} originAirport - Airport object with lat/lon
 * @param {Object} destAirport - Airport object with lat/lon
 * @param {string} fareClass - Fare class ('standard', 'flex', 'superflex')
 * @param {Object} options - Additional pricing options (peak, weekend, holiday)
 * @returns {Object} Pricing details with distance and fare breakdown
 */
function calculateFlightPrice(originAirport, destAirport, fareClass = 'standard', options = {}) {
    if (!originAirport || !destAirport) {
        return { error: 'Missing airport data' };
    }
    
    if (!originAirport.lat || !originAirport.lon || !destAirport.lat || !destAirport.lon) {
        return { error: 'Missing airport coordinates' };
    }
    
    // Calculate distance
    const distance = calculateDistance(
        originAirport.lat, 
        originAirport.lon, 
        destAirport.lat, 
        destAirport.lon
    );
    
    // Calculate base fare
    let fare = calculateBaseFare(distance);
    
    // Apply fare class multiplier
    fare = applyFareClass(fare, fareClass);
    
    // Apply optional surcharges
    if (options.peak) fare *= PRICING_CONFIG.surcharges.peak;
    if (options.weekend) fare *= PRICING_CONFIG.surcharges.weekend;
    if (options.holiday) fare *= PRICING_CONFIG.surcharges.holiday;
    
    // Round to nearest dollar
    fare = Math.round(fare);
    
    return {
        distance: distance,
        distanceUnit: 'km',
        baseFare: Math.round(calculateBaseFare(distance)),
        fareClass: fareClass,
        fareClassName: PRICING_CONFIG.fareClasses[fareClass]?.name || fareClass,
        finalFare: fare,
        currency: 'USD',
        pricePerKm: PRICING_CONFIG.pricePerKm,
        surcharges: options
    };
}

/**
 * Get all fare class prices for a route
 * @param {Object} originAirport - Airport object with lat/lon
 * @param {Object} destAirport - Airport object with lat/lon
 * @param {Object} options - Additional pricing options
 * @returns {Object} All fare classes with prices
 */
function getAllFareClassPrices(originAirport, destAirport, options = {}) {
    const fares = {};
    
    for (const [key, config] of Object.entries(PRICING_CONFIG.fareClasses)) {
        const pricing = calculateFlightPrice(originAirport, destAirport, key, options);
        fares[key] = {
            ...pricing,
            description: config.description
        };
    }
    
    return fares;
}

/**
 * Find airport by IATA code from airports array
 * @param {string} iataCode - 3-letter IATA code
 * @param {Array} airports - Array of airport objects
 * @returns {Object|null} Airport object or null if not found
 */
function findAirportByCode(iataCode, airports) {
    if (!iataCode || !airports) return null;
    const code = iataCode.toUpperCase();
    return airports.find(a => a.code && a.code.toUpperCase() === code) || null;
}

/**
 * Format price for display
 * @param {number} price - Price amount
 * @param {string} currency - Currency code
 * @returns {string} Formatted price string
 */
function formatPrice(price, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(price);
}

/**
 * Format distance for display
 * @param {number} distance - Distance in kilometers
 * @returns {string} Formatted distance string
 */
function formatDistance(distance) {
    return new Intl.NumberFormat('en-US').format(distance) + ' km';
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.FlightPricing = {
        config: PRICING_CONFIG,
        calculateDistance,
        calculateBaseFare,
        applyFareClass,
        calculateFlightPrice,
        getAllFareClassPrices,
        findAirportByCode,
        formatPrice,
        formatDistance
    };
}
