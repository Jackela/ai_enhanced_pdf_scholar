/**
 * Documentation Search Index and Functionality
 * 
 * This script provides client-side search capabilities for the AI Enhanced PDF Scholar documentation.
 * Features include fuzzy search, content indexing, and real-time search results.
 */

class DocumentationSearchIndex {
    constructor() {
        this.index = new Map();
        this.documents = new Map();
        this.searchHistory = [];
        this.maxHistorySize = 50;
        this.initialized = false;
        this.searchCache = new Map();
        
        console.log('📚 Documentation Search Index initialized');
        this.initializeSearch();
    }
    
    /**
     * Initialize the search system
     */
    async initializeSearch() {
        try {
            // Load search index data
            await this.loadSearchIndex();
            
            // Set up search UI if DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.setupSearchUI());
            } else {
                this.setupSearchUI();
            }
            
            this.initialized = true;
            console.log('✅ Documentation search system ready');
            
        } catch (error) {
            console.error('❌ Failed to initialize search system:', error);
        }
    }
    
    /**
     * Load search index from generated data
     */
    async loadSearchIndex() {
        try {
            // Try to load pre-generated search index
            const response = await fetch('/docs/assets/data/search-index.json');
            if (response.ok) {
                const data = await response.json();
                this.processSearchIndex(data);
                console.log(`📖 Loaded search index with ${data.documents.length} documents`);
                return;
            }
        } catch (error) {
            console.log('No pre-generated index found, building from DOM...');
        }
        
        // Fallback: build index from current page content
        this.buildIndexFromDOM();
    }
    
    /**
     * Process loaded search index data
     */
    processSearchIndex(data) {
        // Clear existing data
        this.index.clear();
        this.documents.clear();
        
        // Process documents
        data.documents.forEach(doc => {
            this.documents.set(doc.id, doc);
            
            // Build word index
            const words = this.extractWords(doc.content);
            words.forEach(word => {
                const normalizedWord = this.normalizeWord(word);
                if (normalizedWord.length > 2) { // Skip very short words
                    if (!this.index.has(normalizedWord)) {
                        this.index.set(normalizedWord, new Set());
                    }
                    this.index.get(normalizedWord).add(doc.id);
                }
            });
        });
    }
    
    /**
     * Build search index from current DOM content
     */
    buildIndexFromDOM() {
        const content = document.body.textContent || document.body.innerText || '';
        const title = document.title || 'Documentation';
        const url = window.location.pathname;
        
        const doc = {
            id: this.generateId(url),
            title: title,
            url: url,
            content: content,
            section: this.extractSection(url),
            lastModified: new Date().toISOString()
        };
        
        this.documents.set(doc.id, doc);
        
        // Build word index for current page
        const words = this.extractWords(content);
        words.forEach(word => {
            const normalizedWord = this.normalizeWord(word);
            if (normalizedWord.length > 2) {
                if (!this.index.has(normalizedWord)) {
                    this.index.set(normalizedWord, new Set());
                }
                this.index.get(normalizedWord).add(doc.id);
            }
        });
        
        console.log('📝 Built search index from current page');
    }
    
    /**
     * Set up search user interface
     */
    setupSearchUI() {
        // Create search container if it doesn't exist
        let searchContainer = document.getElementById('docs-search-container');
        if (!searchContainer) {
            searchContainer = this.createSearchUI();
            this.insertSearchUI(searchContainer);
        }
        
        // Set up event listeners
        this.setupSearchEvents(searchContainer);
        
        // Load search history
        this.loadSearchHistory();
    }
    
    /**
     * Create search UI elements
     */
    createSearchUI() {
        const container = document.createElement('div');
        container.id = 'docs-search-container';
        container.className = 'docs-search-container';
        
        container.innerHTML = `
            <div class="search-input-group">
                <input type="text" 
                       id="docs-search-input" 
                       class="search-input"
                       placeholder="Search documentation..." 
                       autocomplete="off"
                       aria-label="Search documentation">
                <button id="docs-search-button" class="search-button" aria-label="Search">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="11" cy="11" r="8"></circle>
                        <path d="m21 21-4.35-4.35"></path>
                    </svg>
                </button>
                <button id="docs-search-clear" class="search-clear hidden" aria-label="Clear search">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
            
            <div id="docs-search-results" class="search-results hidden">
                <div class="search-results-header">
                    <span id="search-results-count">0 results</span>
                    <span id="search-results-time"></span>
                </div>
                <ul id="search-results-list" class="search-results-list"></ul>
                <div id="search-no-results" class="search-no-results hidden">
                    <p>No results found. Try different keywords or check our <a href="/docs/user-guide/getting-started.md">Getting Started Guide</a>.</p>
                </div>
            </div>
            
            <div id="docs-search-suggestions" class="search-suggestions hidden">
                <div class="suggestions-header">Recent searches</div>
                <ul id="search-suggestions-list" class="suggestions-list"></ul>
            </div>
        `;
        
        return container;
    }
    
    /**
     * Insert search UI into the page
     */
    insertSearchUI(container) {
        // Try to find navigation or header element
        const nav = document.querySelector('nav') || 
                   document.querySelector('header') || 
                   document.querySelector('.header') ||
                   document.querySelector('.navigation');
        
        if (nav) {
            nav.appendChild(container);
        } else {
            // Insert at the beginning of main content
            const main = document.querySelector('main') || 
                         document.querySelector('.main') ||
                         document.body;
            main.insertBefore(container, main.firstChild);
        }
    }
    
    /**
     * Set up search event listeners
     */
    setupSearchEvents(container) {
        const searchInput = container.querySelector('#docs-search-input');
        const searchButton = container.querySelector('#docs-search-button');
        const searchClear = container.querySelector('#docs-search-clear');
        const resultsContainer = container.querySelector('#docs-search-results');
        const suggestionsContainer = container.querySelector('#docs-search-suggestions');
        
        let searchTimeout;
        
        // Search input events
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            
            // Clear previous timeout
            clearTimeout(searchTimeout);
            
            // Show/hide clear button
            if (query) {
                searchClear.classList.remove('hidden');
            } else {
                searchClear.classList.add('hidden');
                this.hideSearchResults();
                return;
            }
            
            // Debounced search
            searchTimeout = setTimeout(() => {
                this.performSearch(query);
            }, 300);
        });
        
        // Search button click
        searchButton.addEventListener('click', () => {
            const query = searchInput.value.trim();
            if (query) {
                this.performSearch(query);
            }
        });
        
        // Clear button click
        searchClear.addEventListener('click', () => {
            searchInput.value = '';
            searchClear.classList.add('hidden');
            this.hideSearchResults();
            searchInput.focus();
        });
        
        // Keyboard shortcuts
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const query = searchInput.value.trim();
                if (query) {
                    this.performSearch(query);
                }
            } else if (e.key === 'Escape') {
                this.hideSearchResults();
                searchInput.blur();
            }
        });
        
        // Focus events for suggestions
        searchInput.addEventListener('focus', () => {
            if (!searchInput.value.trim()) {
                this.showSearchSuggestions();
            }
        });
        
        searchInput.addEventListener('blur', (e) => {
            // Delay hiding to allow clicking on results
            setTimeout(() => {
                if (!e.relatedTarget || !container.contains(e.relatedTarget)) {
                    this.hideSearchResults();
                    this.hideSearchSuggestions();
                }
            }, 100);
        });
        
        // Global keyboard shortcut (Ctrl+K or Cmd+K)
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
        });
    }
    
    /**
     * Perform search and display results
     */
    async performSearch(query) {
        const startTime = performance.now();
        
        try {
            // Check cache first
            if (this.searchCache.has(query)) {
                const cachedResults = this.searchCache.get(query);
                this.displaySearchResults(cachedResults, query, performance.now() - startTime);
                return;
            }
            
            // Perform search
            const results = this.search(query);
            
            // Cache results
            this.searchCache.set(query, results);
            
            // Limit cache size
            if (this.searchCache.size > 100) {
                const firstKey = this.searchCache.keys().next().value;
                this.searchCache.delete(firstKey);
            }
            
            // Display results
            this.displaySearchResults(results, query, performance.now() - startTime);
            
            // Add to search history
            this.addToSearchHistory(query);
            
        } catch (error) {
            console.error('Search error:', error);
            this.displaySearchError('An error occurred while searching. Please try again.');
        }
    }
    
    /**
     * Core search algorithm
     */
    search(query, options = {}) {
        const {
            maxResults = 20,
            fuzzyThreshold = 0.6,
            boostExactMatch = 2.0,
            boostTitleMatch = 1.5
        } = options;
        
        const queryWords = this.extractWords(query);
        const results = new Map();
        
        // Search for each word
        queryWords.forEach(word => {
            const normalizedWord = this.normalizeWord(word);
            
            // Exact matches
            if (this.index.has(normalizedWord)) {
                this.index.get(normalizedWord).forEach(docId => {
                    if (!results.has(docId)) {
                        results.set(docId, { score: 0, matches: [] });
                    }
                    results.get(docId).score += boostExactMatch;
                    results.get(docId).matches.push({ word, type: 'exact' });
                });
            }
            
            // Fuzzy matches
            for (const [indexWord, docIds] of this.index) {
                const similarity = this.calculateSimilarity(normalizedWord, indexWord);
                if (similarity >= fuzzyThreshold && similarity < 1.0) {
                    docIds.forEach(docId => {
                        if (!results.has(docId)) {
                            results.set(docId, { score: 0, matches: [] });
                        }
                        results.get(docId).score += similarity;
                        results.get(docId).matches.push({ 
                            word, 
                            indexWord, 
                            type: 'fuzzy', 
                            similarity 
                        });
                    });
                }
            }
        });
        
        // Convert to array and enhance with document data
        const resultArray = Array.from(results.entries()).map(([docId, searchData]) => {
            const doc = this.documents.get(docId);
            if (!doc) return null;
            
            // Boost score for title matches
            const titleLower = doc.title.toLowerCase();
            const queryLower = query.toLowerCase();
            if (titleLower.includes(queryLower)) {
                searchData.score *= boostTitleMatch;
            }
            
            return {
                document: doc,
                score: searchData.score,
                matches: searchData.matches,
                excerpt: this.generateExcerpt(doc.content, queryWords)
            };
        }).filter(result => result !== null);
        
        // Sort by relevance score
        resultArray.sort((a, b) => b.score - a.score);
        
        // Return top results
        return resultArray.slice(0, maxResults);
    }
    
    /**
     * Display search results in the UI
     */
    displaySearchResults(results, query, searchTime) {
        const resultsContainer = document.getElementById('docs-search-results');
        const resultsCount = document.getElementById('search-results-count');
        const resultsTime = document.getElementById('search-results-time');
        const resultsList = document.getElementById('search-results-list');
        const noResults = document.getElementById('search-no-results');
        
        // Update count and time
        resultsCount.textContent = `${results.length} result${results.length !== 1 ? 's' : ''}`;
        resultsTime.textContent = `(${searchTime.toFixed(0)}ms)`;
        
        // Clear previous results
        resultsList.innerHTML = '';
        
        if (results.length === 0) {
            noResults.classList.remove('hidden');
        } else {
            noResults.classList.add('hidden');
            
            // Generate result items
            results.forEach((result, index) => {
                const listItem = this.createResultItem(result, query, index);
                resultsList.appendChild(listItem);
            });
        }
        
        // Show results container
        resultsContainer.classList.remove('hidden');
        this.hideSearchSuggestions();
    }
    
    /**
     * Create a search result item
     */
    createResultItem(result, query, index) {
        const li = document.createElement('li');
        li.className = 'search-result-item';
        
        const titleHighlighted = this.highlightText(result.document.title, query);
        const excerptHighlighted = this.highlightText(result.excerpt, query);
        
        li.innerHTML = `
            <div class="result-header">
                <a href="${result.document.url}" class="result-title" tabindex="0">
                    ${titleHighlighted}
                </a>
                <span class="result-score" title="Relevance score">${result.score.toFixed(2)}</span>
            </div>
            <div class="result-meta">
                <span class="result-section">${result.document.section}</span>
                <span class="result-url">${result.document.url}</span>
            </div>
            <div class="result-excerpt">${excerptHighlighted}</div>
            ${result.matches.length > 0 ? `
                <div class="result-matches">
                    ${result.matches.slice(0, 3).map(match => 
                        `<span class="match-badge ${match.type}">${match.word}</span>`
                    ).join('')}
                </div>
            ` : ''}
        `;
        
        // Add keyboard navigation
        const link = li.querySelector('.result-title');
        link.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                window.location.href = result.document.url;
            }
        });
        
        return li;
    }
    
    /**
     * Display search error
     */
    displaySearchError(message) {
        const resultsContainer = document.getElementById('docs-search-results');
        const resultsList = document.getElementById('search-results-list');
        
        resultsList.innerHTML = `
            <li class="search-error">
                <div class="error-icon">⚠️</div>
                <div class="error-message">${message}</div>
            </li>
        `;
        
        resultsContainer.classList.remove('hidden');
    }
    
    /**
     * Hide search results
     */
    hideSearchResults() {
        const resultsContainer = document.getElementById('docs-search-results');
        if (resultsContainer) {
            resultsContainer.classList.add('hidden');
        }
    }
    
    /**
     * Show search suggestions
     */
    showSearchSuggestions() {
        if (this.searchHistory.length === 0) return;
        
        const suggestionsContainer = document.getElementById('docs-search-suggestions');
        const suggestionsList = document.getElementById('search-suggestions-list');
        
        suggestionsList.innerHTML = '';
        
        this.searchHistory.slice(0, 5).forEach(query => {
            const li = document.createElement('li');
            li.className = 'suggestion-item';
            li.innerHTML = `
                <button class="suggestion-button" data-query="${this.escapeHtml(query)}">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 12h18m-9-9l9 9l-9 9"></path>
                    </svg>
                    ${this.escapeHtml(query)}
                </button>
            `;
            
            li.addEventListener('click', () => {
                const searchInput = document.getElementById('docs-search-input');
                searchInput.value = query;
                this.performSearch(query);
            });
            
            suggestionsList.appendChild(li);
        });
        
        suggestionsContainer.classList.remove('hidden');
    }
    
    /**
     * Hide search suggestions
     */
    hideSearchSuggestions() {
        const suggestionsContainer = document.getElementById('docs-search-suggestions');
        if (suggestionsContainer) {
            suggestionsContainer.classList.add('hidden');
        }
    }
    
    /**
     * Add query to search history
     */
    addToSearchHistory(query) {
        // Remove if already exists
        const index = this.searchHistory.indexOf(query);
        if (index > -1) {
            this.searchHistory.splice(index, 1);
        }
        
        // Add to beginning
        this.searchHistory.unshift(query);
        
        // Limit size
        if (this.searchHistory.length > this.maxHistorySize) {
            this.searchHistory = this.searchHistory.slice(0, this.maxHistorySize);
        }
        
        // Save to localStorage
        this.saveSearchHistory();
    }
    
    /**
     * Load search history from localStorage
     */
    loadSearchHistory() {
        try {
            const stored = localStorage.getItem('docs-search-history');
            if (stored) {
                this.searchHistory = JSON.parse(stored);
            }
        } catch (error) {
            console.warn('Failed to load search history:', error);
        }
    }
    
    /**
     * Save search history to localStorage
     */
    saveSearchHistory() {
        try {
            localStorage.setItem('docs-search-history', JSON.stringify(this.searchHistory));
        } catch (error) {
            console.warn('Failed to save search history:', error);
        }
    }
    
    // Utility methods
    
    /**
     * Extract words from text
     */
    extractWords(text) {
        return text.toLowerCase()
                  .replace(/[^\w\s-]/g, ' ')
                  .split(/\s+/)
                  .filter(word => word.length > 0);
    }
    
    /**
     * Normalize word for indexing
     */
    normalizeWord(word) {
        return word.toLowerCase().trim();
    }
    
    /**
     * Calculate similarity between two strings using Levenshtein distance
     */
    calculateSimilarity(str1, str2) {
        const longer = str1.length > str2.length ? str1 : str2;
        const shorter = str1.length > str2.length ? str2 : str1;
        
        if (longer.length === 0) return 1.0;
        
        const distance = this.levenshteinDistance(longer, shorter);
        return (longer.length - distance) / longer.length;
    }
    
    /**
     * Calculate Levenshtein distance
     */
    levenshteinDistance(str1, str2) {
        const matrix = [];
        
        for (let i = 0; i <= str2.length; i++) {
            matrix[i] = [i];
        }
        
        for (let j = 0; j <= str1.length; j++) {
            matrix[0][j] = j;
        }
        
        for (let i = 1; i <= str2.length; i++) {
            for (let j = 1; j <= str1.length; j++) {
                if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j] + 1
                    );
                }
            }
        }
        
        return matrix[str2.length][str1.length];
    }
    
    /**
     * Generate excerpt from content
     */
    generateExcerpt(content, queryWords, maxLength = 200) {
        const sentences = content.split(/[.!?]+/);
        let bestSentence = '';
        let maxMatches = 0;
        
        // Find sentence with most query word matches
        sentences.forEach(sentence => {
            const sentenceLower = sentence.toLowerCase();
            let matches = 0;
            
            queryWords.forEach(word => {
                if (sentenceLower.includes(word.toLowerCase())) {
                    matches++;
                }
            });
            
            if (matches > maxMatches) {
                maxMatches = matches;
                bestSentence = sentence.trim();
            }
        });
        
        // If no matches found, use beginning of content
        if (maxMatches === 0) {
            bestSentence = content.substring(0, maxLength);
        }
        
        // Truncate if too long
        if (bestSentence.length > maxLength) {
            bestSentence = bestSentence.substring(0, maxLength - 3) + '...';
        }
        
        return bestSentence;
    }
    
    /**
     * Highlight search terms in text
     */
    highlightText(text, query) {
        const queryWords = this.extractWords(query);
        let highlightedText = text;
        
        queryWords.forEach(word => {
            const regex = new RegExp(`(${this.escapeRegex(word)})`, 'gi');
            highlightedText = highlightedText.replace(regex, '<mark>$1</mark>');
        });
        
        return highlightedText;
    }
    
    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Escape regex
     */
    escapeRegex(text) {
        return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
    
    /**
     * Generate unique ID
     */
    generateId(text) {
        return btoa(text).replace(/[^a-zA-Z0-9]/g, '').substring(0, 16);
    }
    
    /**
     * Extract section from URL
     */
    extractSection(url) {
        const parts = url.split('/');
        if (parts.length > 2) {
            return parts[parts.length - 2].replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }
        return 'Documentation';
    }
}

// CSS styles for search UI
const searchStyles = `
    .docs-search-container {
        position: relative;
        margin: 1rem 0;
        max-width: 600px;
    }
    
    .search-input-group {
        position: relative;
        display: flex;
        align-items: center;
        background: #f8f9fa;
        border: 2px solid #e9ecef;
        border-radius: 8px;
        transition: border-color 0.2s ease;
    }
    
    .search-input-group:focus-within {
        border-color: #0066cc;
        box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
    }
    
    .search-input {
        flex: 1;
        padding: 12px 16px;
        border: none;
        background: transparent;
        font-size: 16px;
        outline: none;
    }
    
    .search-button,
    .search-clear {
        padding: 8px;
        border: none;
        background: transparent;
        cursor: pointer;
        color: #6c757d;
        transition: color 0.2s ease;
    }
    
    .search-button:hover,
    .search-clear:hover {
        color: #495057;
    }
    
    .search-results {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        max-height: 400px;
        overflow-y: auto;
    }
    
    .search-results-header {
        display: flex;
        justify-content: space-between;
        padding: 12px 16px;
        background: #f8f9fa;
        border-bottom: 1px solid #dee2e6;
        font-size: 14px;
        color: #6c757d;
    }
    
    .search-results-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    
    .search-result-item {
        padding: 16px;
        border-bottom: 1px solid #f1f3f4;
        cursor: pointer;
        transition: background-color 0.2s ease;
    }
    
    .search-result-item:hover {
        background: #f8f9fa;
    }
    
    .search-result-item:last-child {
        border-bottom: none;
    }
    
    .result-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 8px;
    }
    
    .result-title {
        color: #0066cc;
        text-decoration: none;
        font-weight: 600;
        font-size: 16px;
        line-height: 1.3;
    }
    
    .result-title:hover {
        text-decoration: underline;
    }
    
    .result-score {
        font-size: 12px;
        color: #adb5bd;
        background: #e9ecef;
        padding: 2px 6px;
        border-radius: 12px;
    }
    
    .result-meta {
        display: flex;
        gap: 12px;
        margin-bottom: 8px;
        font-size: 13px;
        color: #6c757d;
    }
    
    .result-section {
        font-weight: 500;
    }
    
    .result-url {
        font-family: monospace;
    }
    
    .result-excerpt {
        color: #495057;
        line-height: 1.4;
        margin-bottom: 8px;
    }
    
    .result-matches {
        display: flex;
        gap: 4px;
        flex-wrap: wrap;
    }
    
    .match-badge {
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 500;
    }
    
    .match-badge.exact {
        background: #d1ecf1;
        color: #0c5460;
    }
    
    .match-badge.fuzzy {
        background: #fff3cd;
        color: #856404;
    }
    
    .search-no-results {
        padding: 32px 16px;
        text-align: center;
        color: #6c757d;
    }
    
    .search-suggestions {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 1000;
    }
    
    .suggestions-header {
        padding: 12px 16px;
        background: #f8f9fa;
        border-bottom: 1px solid #dee2e6;
        font-size: 14px;
        color: #6c757d;
        font-weight: 500;
    }
    
    .suggestions-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    
    .suggestion-item {
        border-bottom: 1px solid #f1f3f4;
    }
    
    .suggestion-item:last-child {
        border-bottom: none;
    }
    
    .suggestion-button {
        width: 100%;
        padding: 12px 16px;
        border: none;
        background: transparent;
        text-align: left;
        cursor: pointer;
        transition: background-color 0.2s ease;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .suggestion-button:hover {
        background: #f8f9fa;
    }
    
    .search-error {
        padding: 32px 16px;
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
    }
    
    .error-icon {
        font-size: 32px;
    }
    
    .error-message {
        color: #dc3545;
        font-weight: 500;
    }
    
    .hidden {
        display: none !important;
    }
    
    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .search-input-group {
            background: #2d3748;
            border-color: #4a5568;
        }
        
        .search-input {
            color: #e2e8f0;
        }
        
        .search-results,
        .search-suggestions {
            background: #2d3748;
            border-color: #4a5568;
        }
        
        .search-results-header,
        .suggestions-header {
            background: #1a202c;
            border-color: #4a5568;
        }
        
        .search-result-item:hover,
        .suggestion-button:hover {
            background: #1a202c;
        }
        
        .result-title {
            color: #63b3ed;
        }
        
        .result-excerpt {
            color: #cbd5e0;
        }
        
        .result-meta {
            color: #a0aec0;
        }
    }
    
    mark {
        background: #ffeb3b;
        color: #000;
        padding: 1px 2px;
        border-radius: 2px;
    }
    
    @media (prefers-color-scheme: dark) {
        mark {
            background: #f59e0b;
            color: #1a202c;
        }
    }
`;

// Inject styles
const styleSheet = document.createElement('style');
styleSheet.textContent = searchStyles;
document.head.appendChild(styleSheet);

// Initialize search when DOM is ready
let searchIndex;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        searchIndex = new DocumentationSearchIndex();
    });
} else {
    searchIndex = new DocumentationSearchIndex();
}

// Export for external use
window.DocumentationSearchIndex = DocumentationSearchIndex;
window.docsSearchIndex = searchIndex;