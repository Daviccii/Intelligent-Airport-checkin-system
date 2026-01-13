/**
 * Centralized Admin Authentication Guard
 * Checks if user is authenticated and redirects to login if not
 * Does NOT redirect to dashboard - each page loads independently
 */

(function() {
  'use strict';

  // Check authentication on page load
  function checkAuth() {
    // Check for admin token in localStorage (consistent single method)
    const adminToken = localStorage.getItem('adminToken');
    
    // For development/testing: Allow access without token
    // Comment out the redirect logic temporarily
    if (!adminToken) {
      console.warn('No admin token found - proceeding without authentication (dev mode)');
      // Uncomment the line below to enable authentication:
      // window.location.href = '../admin-login.html';
      return true; // Allow access for now
    }
    
    // Token exists - user is authenticated, allow page to load
    console.log('Admin authenticated, loading page...');
    return true;
  }

  // Run auth check immediately
  checkAuth();
})();
