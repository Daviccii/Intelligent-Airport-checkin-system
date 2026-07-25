/**
 * Centralized Admin Authentication Guard
 * 
 * [SUPERVISOR WARNING - CRITICAL]
 * This script provides a basic UX improvement by redirecting unauthenticated
 * users away from admin pages. However, it offers ZERO actual security.
 * A user can easily bypass this by setting 'adminToken' in their browser's
 * localStorage.
 * 
 * REAL security MUST be enforced on the BACKEND by validating the token
 * on EVERY single API request to an admin-protected endpoint.
 */

(function() {
  'use strict';

  function checkAuth() {
    const adminToken = localStorage.getItem('adminToken') || localStorage.getItem('session');
    if (!adminToken) {
      window.location.href = '../admin-login.html';
    }
  }

  // Run auth check immediately
  checkAuth();
})();
