/**
 * Centralized Admin Authentication Guard
 * Checks if user is authenticated and redirects to login if not
 * Does NOT redirect to dashboard - each page loads independently
 */

(function() {
  'use strict';

  // Check authentication on page load
  function checkAuth() {
    const adminToken = localStorage.getItem('adminToken') || localStorage.getItem('session');
    if (!adminToken) {
      window.location.href = '../admin-login.html';
      return false;
    }
    return true;
    
    // Token exists - user is authenticated, allow page to load
    console.log('Admin authenticated, loading page...');
    return true;
  }

  // Run auth check immediately
  checkAuth();
})();
