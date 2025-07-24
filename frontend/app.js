/**
 * Customer Support Intelligence Frontend Application
 * 
 * This is the main JavaScript file that handles all client-side functionality
 * for the Customer Support Intelligence dashboard. It provides a complete
 * interface for creating, viewing, and managing support tickets with AI classification.
 * 
 * Key Features:
 * - Real-time ticket creation with AI classification
 * - Dynamic filtering and pagination
 * - Statistics dashboard with visual metrics
 * - Responsive Bootstrap UI components
 * - Error handling and loading states
 */

// ========================================
// CONFIGURATION & CONSTANTS
// ========================================

/**
 * Base URL for the Customer Support Intelligence API
 * Change this if your API server is running on a different host/port
 */
const API_BASE_URL = 'http://localhost:8000/api/v1';

// ========================================
// GLOBAL APPLICATION STATE
// ========================================

/**
 * Application state variables that track the current view and filtering options
 * These variables maintain consistency across different UI operations
 */
let currentOffset = 0;      // Current pagination offset for ticket list
let currentLimit = 25;      // Number of tickets to display per page
let currentCategory = '';   // Currently selected category filter (empty = all)
let totalTickets = 0;       // Total number of tickets matching current filters

// ========================================
// UTILITY FUNCTIONS
// ========================================

/**
 * Shows or hides a loading spinner element
 * 
 * @param {string} elementId - The ID of the HTML element containing the loading indicator
 * @param {boolean} show - Whether to show (true) or hide (false) the loading indicator
 */
function showLoading(elementId, show = true) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.display = show ? 'block' : 'none';
    }
}

/**
 * Displays a Bootstrap alert message with auto-dismiss functionality
 * 
 * @param {string} containerId - The ID of the container element to display the alert in
 * @param {string} message - The HTML message content to display
 * @param {string} type - Bootstrap alert type ('success', 'danger', 'warning', 'info')
 */
function showAlert(containerId, message, type = 'success') {
    const container = document.getElementById(containerId);
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    container.innerHTML = '';
    container.appendChild(alertDiv);
    
    // Auto dismiss after 5 seconds for better UX
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

/**
 * Formats an ISO date string to a localized date/time string
 * 
 * @param {string} dateString - ISO 8601 formatted date string from the API
 * @returns {string} Localized date and time string
 */
function formatDate(dateString) {
    return new Date(dateString).toLocaleString();
}

/**
 * Returns the appropriate Bootstrap CSS class for category badges
 * Each category has a distinct color scheme for visual differentiation
 * 
 * @param {string} category - The ticket category ('technical', 'billing', 'general')
 * @returns {string} Bootstrap CSS classes for the badge
 */
function getCategoryBadgeClass(category) {
    const classes = {
        'technical': 'bg-primary',           // Blue for technical issues
        'billing': 'bg-success',             // Green for billing inquiries
        'general': 'bg-warning text-dark'    // Yellow for general questions
    };
    return classes[category] || 'bg-secondary';  // Gray fallback for unknown categories
}

/**
 * Converts a decimal confidence score to a formatted percentage string
 * 
 * @param {number|null} score - Confidence score from AI classification (0.0 to 1.0)
 * @returns {string} Formatted percentage string or empty string if no score
 */
function formatConfidenceScore(score) {
    if (!score) return '';
    return `${(score * 100).toFixed(1)}%`;
}

// ========================================
// API COMMUNICATION LAYER
// ========================================

/**
 * Generic function to make HTTP requests to the Customer Support Intelligence API
 * Handles JSON serialization, error responses, and network failures consistently
 * 
 * @param {string} endpoint - API endpoint path (relative to API_BASE_URL)
 * @param {string} method - HTTP method ('GET', 'POST', 'PUT', 'DELETE')
 * @param {Object|null} data - Request body data (will be JSON stringified)
 * @returns {Promise<Object>} Parsed JSON response from the API
 * @throws {Error} If the request fails or returns an error status
 */
async function makeApiCall(endpoint, method = 'GET', data = null) {
    const url = `${API_BASE_URL}${endpoint}`;
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(url, options);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

/**
 * Creates a new support ticket via the API
 * 
 * @param {Object} ticketData - Ticket information containing subject and body
 * @returns {Promise<Object>} Created ticket object with ID and classification
 */
async function createTicket(ticketData) {
    return await makeApiCall('/requests/', 'POST', ticketData);
}

/**
 * Retrieves a paginated list of support tickets with optional category filtering
 * 
 * @param {string} category - Category filter ('technical', 'billing', 'general', or empty for all)
 * @param {number} limit - Maximum number of tickets to return (default: 25)
 * @param {number} offset - Number of tickets to skip for pagination (default: 0)
 * @returns {Promise<Object>} Object containing items array and total count
 */
async function getTickets(category = '', limit = 25, offset = 0) {
    let endpoint = `/requests/?limit=${limit}&offset=${offset}`;
    if (category) {
        endpoint += `&category=${category}`;
    }
    return await makeApiCall(endpoint);
}

/**
 * Retrieves detailed information for a specific support ticket
 * 
 * @param {number} id - The unique identifier of the ticket
 * @returns {Promise<Object>} Complete ticket object with classification details
 */
async function getTicket(id) {
    return await makeApiCall(`/requests/${id}`);
}

/**
 * Retrieves dashboard statistics for a specified time period
 * 
 * @param {number} days - Number of days to include in statistics (default: 7)
 * @returns {Promise<Object>} Statistics object with totals, averages, and category breakdowns
 */
async function getStats(days = 7) {
    return await makeApiCall(`/stats/?days=${days}`);
}

// ========================================
// UI RENDERING FUNCTIONS
// ========================================

/**
 * Renders the dashboard statistics cards with ticket metrics
 * Creates responsive Bootstrap cards showing total tickets, confidence scores, and category breakdowns
 * 
 * @param {Object} stats - Statistics data from the API containing totals and category breakdowns
 */
function renderStats(stats) {
    const statsSection = document.getElementById('stats-section');
    
    const statsHtml = `
        <div class="col-md-3">
            <div class="card stats-card bg-primary text-white">
                <div class="card-body">
                    <div class="d-flex justify-content-between">
                        <div>
                            <h6 class="card-title">Total Tickets</h6>
                            <h3 class="mb-0">${stats.total_tickets}</h3>
                        </div>
                        <div>
                            <i class="bi bi-ticket-perforated" style="font-size: 2rem;"></i>
                        </div>
                    </div>
                    <small>Last ${stats.period_days} days</small>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card stats-card bg-success text-white">
                <div class="card-body">
                    <div class="d-flex justify-content-between">
                        <div>
                            <h6 class="card-title">Avg Confidence</h6>
                            <h3 class="mb-0">${formatConfidenceScore(stats.average_confidence)}</h3>
                        </div>
                        <div>
                            <i class="bi bi-graph-up" style="font-size: 2rem;"></i>
                        </div>
                    </div>
                    <small>AI Classification</small>
                </div>
            </div>
        </div>
        ${stats.categories.map((cat, index) => {
            const colors = ['bg-info', 'bg-warning', 'bg-secondary'];
            const color = colors[index] || 'bg-secondary';
            const textClass = color === 'bg-warning' ? 'text-dark' : 'text-white';
            return `
                <div class="col-md-3">
                    <div class="card stats-card ${color} ${textClass}">
                        <div class="card-body">
                            <div class="d-flex justify-content-between">
                                <div>
                                    <h6 class="card-title">${cat.category.charAt(0).toUpperCase() + cat.category.slice(1)}</h6>
                                    <h3 class="mb-0">${cat.count}</h3>
                                </div>
                                <div>
                                    <i class="bi bi-pie-chart" style="font-size: 2rem;"></i>
                                </div>
                            </div>
                            <small>${cat.percentage.toFixed(1)}% of total</small>
                        </div>
                    </div>
                </div>
            `;
        }).slice(0, 2).join('')}
    `;
    
    statsSection.innerHTML = statsHtml;
}

/**
 * Renders the list of support tickets in responsive card format
 * Each ticket displays key information, classification results, and action buttons
 * Handles empty states with user-friendly messaging
 * 
 * @param {Array} tickets - Array of ticket objects from the API
 */
function renderTickets(tickets) {
    const ticketsList = document.getElementById('tickets-list');
    
    if (tickets.length === 0) {
        ticketsList.innerHTML = `
            <div class="text-center py-4">
                <i class="bi bi-inbox" style="font-size: 3rem; color: #dee2e6;"></i>
                <h5 class="mt-3 text-muted">No tickets found</h5>
                <p class="text-muted">Try adjusting your filters or create a new ticket.</p>
            </div>
        `;
        return;
    }
    
    const ticketsHtml = tickets.map(ticket => {
        const categoryClass = ticket.classification ? 
            `category-${ticket.classification.category}` : '';
        
        return `
            <div class="card ticket-card mb-3 ${categoryClass}">
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-8">
                            <h6 class="card-title mb-2">
                                ${ticket.subject || 'No Subject'}
                                ${ticket.classification ? `
                                    <span class="badge category-badge ${getCategoryBadgeClass(ticket.classification.category)}">
                                        ${ticket.classification.category}
                                    </span>
                                ` : ''}
                            </h6>
                            <p class="card-text text-muted mb-2">
                                ${ticket.body.length > 150 ? 
                                    ticket.body.substring(0, 150) + '...' : 
                                    ticket.body}
                            </p>
                        </div>
                        <div class="col-md-4 text-md-end">
                            <div class="mb-2">
                                <small class="text-muted">
                                    <i class="bi bi-calendar"></i> ${formatDate(ticket.created_at)}
                                </small>
                            </div>
                            ${ticket.classification ? `
                                <div class="confidence-score mb-2">
                                    <i class="bi bi-speedometer2"></i> 
                                    Confidence: ${formatConfidenceScore(ticket.classification.confidence_score)}
                                </div>
                            ` : ''}
                            <button class="btn btn-sm btn-outline-primary" onclick="viewTicketDetails(${ticket.id})">
                                <i class="bi bi-eye"></i> View Details
                            </button>
                        </div>
                    </div>
                    ${ticket.classification && ticket.classification.summary ? `
                        <div class="mt-2 p-2 bg-light rounded">
                            <small><strong>AI Summary:</strong> ${ticket.classification.summary}</small>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    ticketsList.innerHTML = ticketsHtml;
}

/**
 * Renders Bootstrap pagination controls for ticket navigation
 * Calculates page numbers and generates clickable pagination links
 * 
 * @param {number} total - Total number of tickets matching current filters
 * @param {number} limit - Number of tickets displayed per page
 * @param {number} offset - Current pagination offset
 */
function renderPagination(total, limit, offset) {
    const pagination = document.getElementById('pagination');
    const totalPages = Math.ceil(total / limit);
    const currentPage = Math.floor(offset / limit) + 1;
    
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    let paginationHtml = '<nav><ul class="pagination justify-content-center">';
    
    // Previous button
    if (currentPage > 1) {
        paginationHtml += `
            <li class="page-item">
                <a class="page-link" href="#" onclick="changePage(${currentPage - 1})">Previous</a>
            </li>
        `;
    }
    
    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        paginationHtml += `
            <li class="page-item ${i === currentPage ? 'active' : ''}">
                <a class="page-link" href="#" onclick="changePage(${i})">${i}</a>
            </li>
        `;
    }
    
    // Next button
    if (currentPage < totalPages) {
        paginationHtml += `
            <li class="page-item">
                <a class="page-link" href="#" onclick="changePage(${currentPage + 1})">Next</a>
            </li>
        `;
    }
    
    paginationHtml += '</ul></nav>';
    pagination.innerHTML = paginationHtml;
}

// ========================================
// EVENT HANDLERS & USER INTERACTIONS
// ========================================

/**
 * Handles the submission of new support tickets
 * Manages form validation, loading states, API communication, and user feedback
 * Automatically refreshes the ticket list upon successful creation
 * 
 * @param {Event} event - Form submission event
 */
async function handleTicketSubmit(event) {
    event.preventDefault();
    
    const submitButton = event.target.querySelector('button[type="submit"]');
    const loading = submitButton.querySelector('.loading');
    
    // Show loading state
    loading.style.display = 'inline-block';
    submitButton.disabled = true;
    
    try {
        const formData = {
            subject: document.getElementById('subject').value,
            body: document.getElementById('body').value
        };
        
        const result = await createTicket(formData);
        
        showAlert('create-result', `
            <i class="bi bi-check-circle"></i> 
            Ticket created successfully! ID: ${result.id}
        `, 'success');
        
        // Reset form
        event.target.reset();
        
        // Refresh tickets list
        await loadTickets();
        
    } catch (error) {
        showAlert('create-result', `
            <i class="bi bi-exclamation-triangle"></i> 
            Error creating ticket: ${error.message}
        `, 'danger');
    } finally {
        // Hide loading state
        loading.style.display = 'none';
        submitButton.disabled = false;
    }
}

/**
 * Loads and displays the current page of support tickets
 * Applies current filters and pagination settings, updates UI with results
 * Handles loading states and error conditions gracefully
 */
async function loadTickets() {
    showLoading('tickets-loading', true);
    
    try {
        const category = document.getElementById('category-filter').value;
        const limit = parseInt(document.getElementById('limit').value);
        
        const response = await getTickets(category, limit, currentOffset);
        
        totalTickets = response.total;
        currentLimit = limit;
        currentCategory = category;
        
        renderTickets(response.items);
        renderPagination(response.total, limit, currentOffset);
        
        // Update ticket count
        document.getElementById('ticket-count').textContent = 
            `${response.total} ticket${response.total !== 1 ? 's' : ''}`;
        
    } catch (error) {
        console.error('Error loading tickets:', error);
        document.getElementById('tickets-list').innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> 
                Error loading tickets: ${error.message}
            </div>
        `;
    } finally {
        showLoading('tickets-loading', false);
    }
}

/**
 * Loads and displays dashboard statistics
 * Fetches 7-day statistics and renders them in the stats section
 * Shows error message if statistics cannot be loaded
 */
async function loadStats() {
    try {
        const stats = await getStats(7);
        renderStats(stats);
    } catch (error) {
        console.error('Error loading stats:', error);
        document.getElementById('stats-section').innerHTML = `
            <div class="col-12">
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle"></i> 
                    Unable to load statistics: ${error.message}
                </div>
            </div>
        `;
    }
}

/**
 * Handles pagination navigation by updating the current offset and reloading tickets
 * 
 * @param {number} page - Target page number (1-based)
 */
function changePage(page) {
    currentOffset = (page - 1) * currentLimit;
    loadTickets();
}

/**
 * Displays detailed information for a specific ticket in a Bootstrap modal
 * Fetches complete ticket data including AI classification results and presents
 * it in a user-friendly modal dialog with proper formatting
 * 
 * @param {number} ticketId - The unique identifier of the ticket to display
 */
async function viewTicketDetails(ticketId) {
    try {
        const ticket = await getTicket(ticketId);
        
        // Create modal content
        const modalContent = `
            <div class="modal fade" id="ticketModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                Ticket #${ticket.id} 
                                ${ticket.classification ? `
                                    <span class="badge ${getCategoryBadgeClass(ticket.classification.category)}">
                                        ${ticket.classification.category}
                                    </span>
                                ` : ''}
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row mb-3">
                                <div class="col-sm-3"><strong>Subject:</strong></div>
                                <div class="col-sm-9">${ticket.subject || 'No Subject'}</div>
                            </div>
                            <div class="row mb-3">
                                <div class="col-sm-3"><strong>Created:</strong></div>
                                <div class="col-sm-9">${formatDate(ticket.created_at)}</div>
                            </div>
                            ${ticket.classification ? `
                                <div class="row mb-3">
                                    <div class="col-sm-3"><strong>Category:</strong></div>
                                    <div class="col-sm-9">
                                        ${ticket.classification.category} 
                                        (${formatConfidenceScore(ticket.classification.confidence_score)} confidence)
                                    </div>
                                </div>
                                ${ticket.classification.summary ? `
                                    <div class="row mb-3">
                                        <div class="col-sm-3"><strong>AI Summary:</strong></div>
                                        <div class="col-sm-9">${ticket.classification.summary}</div>
                                    </div>
                                ` : ''}
                            ` : ''}
                            <div class="row mb-3">
                                <div class="col-sm-3"><strong>Description:</strong></div>
                                <div class="col-sm-9">
                                    <div class="border p-3 bg-light rounded" style="white-space: pre-wrap;">${ticket.body}</div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existingModal = document.getElementById('ticketModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalContent);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('ticketModal'));
        modal.show();
        
        // Clean up modal after hiding
        document.getElementById('ticketModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
        
    } catch (error) {
        console.error('Error loading ticket details:', error);
        alert('Error loading ticket details: ' + error.message);
    }
}

// ========================================
// APPLICATION INITIALIZATION
// ========================================

/**
 * Main application initialization function
 * Sets up event listeners, loads initial data, and prepares the UI
 * Runs when the DOM is fully loaded and ready for interaction
 */
document.addEventListener('DOMContentLoaded', function() {
    // Set up form submission
    document.getElementById('ticket-form').addEventListener('submit', handleTicketSubmit);
    
    // Set up filter change handlers
    document.getElementById('category-filter').addEventListener('change', function() {
        currentOffset = 0; // Reset to first page
        loadTickets();
    });
    
    document.getElementById('limit').addEventListener('change', function() {
        currentOffset = 0; // Reset to first page
        loadTickets();
    });
    
    // Load initial data
    loadStats();
    loadTickets();
});