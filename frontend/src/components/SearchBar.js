import React, { useState } from 'react';
import { FiSearch } from 'react-icons/fi';
import './SearchBar.css';

function SearchBar({ onSearch, loading }) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(query);
  };

  const handleChange = (e) => {
    setQuery(e.target.value);
  };

  return (
    <div className="search-bar-container">
      <form onSubmit={handleSubmit} className="search-form">
        <div className="search-input-wrapper">
          <FiSearch className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search documents... (try 'API 617', 'performance', 'revisions', etc.)"
            value={query}
            onChange={handleChange}
            disabled={loading}
            autoFocus
          />
        </div>
        <button 
          type="submit" 
          className="search-button"
          disabled={loading}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>
    </div>
  );
}

export default SearchBar;
