import React, { useState } from 'react';
import { FiChevronDown, FiChevronUp } from 'react-icons/fi';
import './SearchResults.css';

function SearchResults({ results, searchQuery, totalCount }) {
  const [expandedId, setExpandedId] = useState(null);

  const toggleExpand = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const isHtmlContent = (content) => {
    return content.includes('<table') || content.includes('<html');
  };

  const getContentPreview = (content, maxLength = 150) => {
    if (isHtmlContent(content)) {
      // Extract text from HTML for preview
      let text = content.replace(/<[^>]*>/g, ' ').trim();
      text = text.replace(/\s+/g, ' ');
      return text.substring(0, maxLength) + (text.length > maxLength ? '...' : '');
    }
    return content.substring(0, maxLength) + (content.length > maxLength ? '...' : '');
  };

  const getContentType = (content, filename) => {
    if (isHtmlContent(content)) {
      return 'TABLE';
    }
    return 'TEXT';
  };

  return (
    <div className="search-results-container">
      <div className="results-header">
        <h2>Search Results</h2>
        <p className="results-count">Found <strong>{totalCount}</strong> result{totalCount !== 1 ? 's' : ''} for "<strong>{searchQuery}</strong>"</p>
      </div>

      <div className="results-list">
        {results.map((result, index) => (
          <div key={result.id} className="result-item">
            <div 
              className="result-header"
              onClick={() => toggleExpand(result.id)}
            >
              <div className="result-title-section">
                <div className="result-badge">
                  {getContentType(result.content, result.filename)}
                </div>
                <div className="result-info">
                  <h3 className="result-title">{result.filename || `Document ${index + 1}`}</h3>
                  <p className="result-page">Page {result.page_number || 'N/A'}</p>
                </div>
              </div>
              <div className="expand-icon">
                {expandedId === result.id ? <FiChevronUp /> : <FiChevronDown />}
              </div>
            </div>

            <p className="result-preview">{getContentPreview(result.content)}</p>

            {expandedId === result.id && (
              <div className="result-content">
                {isHtmlContent(result.content) ? (
                  <div className="html-table-container">
                    <div dangerouslySetInnerHTML={{ __html: result.content }} />
                  </div>
                ) : (
                  <p className="text-content">{result.content}</p>
                )}
                <div className="result-footer">
                  <span className="char-count">{result.text_length || result.content.length} characters</span>
                  <span className="indexed-date">Indexed: {new Date(result.indexed_date).toLocaleDateString()}</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default SearchResults;
