# KnowBot Search - React Frontend

A modern React-based search interface for Azure AI Search, allowing users to search and browse indexed PDF documents.

## Features

- 🔍 Real-time search across indexed documents
- 📄 Text and HTML table content support
- 📊 Beautiful table rendering with built-in styling
- 🎨 Modern UI with gradient design
- 📱 Responsive design for mobile and desktop
- ⚡ Fast search results with expandable previews

## Getting Started

### Prerequisites
- Node.js (v14 or higher)
- npm or yarn

### Installation

```bash
cd frontend
npm install
```

### Configuration

Create a `.env` file in the frontend directory:

```env
REACT_APP_API_URL=http://localhost:3001/api
```

### Running the Application

**Development Mode:**
```bash
npm start
```

The app will open at [http://localhost:3000](http://localhost:3000)

**Build for Production:**
```bash
npm build
```

## Project Structure

```
frontend/
├── public/
│   └── index.html          # Main HTML file
├── src/
│   ├── components/
│   │   ├── SearchBar.js    # Search input component
│   │   ├── SearchBar.css
│   │   ├── SearchResults.js # Results display component
│   │   └── SearchResults.css
│   ├── App.js              # Main application component
│   ├── App.css
│   ├── index.js            # React entry point
│   └── index.css
├── package.json
└── README.md
```

## Backend Integration

The frontend expects a backend API endpoint at `/api/search` that:

1. Accepts POST requests with:
```json
{
  "query": "search term",
  "top": 20
}
```

2. Returns results in format:
```json
{
  "results": [
    {
      "id": "document_id",
      "content": "document content or HTML",
      "filename": "page_X_text.txt",
      "page_number": 1,
      "indexed_date": "2026-03-13T14:00:00Z",
      "text_length": 1500
    }
  ]
}
```

## Styling

The application uses:
- **Colors:** Purple gradient (#667eea to #764ba2)
- **Fonts:** System fonts for optimal performance
- **Layout:** Flexbox with responsive design
- **Icons:** react-icons library

## Available Scripts

- `npm start` - Runs the app in development mode
- `npm build` - Builds the app for production
- `npm test` - Runs the test suite

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Dependencies

- **react** (18.2.0) - UI library
- **react-dom** (18.2.0) - React DOM rendering
- **axios** (1.6.0) - HTTP client
- **react-icons** (4.12.0) - Icon library

## Future Enhancements

- [ ] Advanced search filters
- [ ] Faceted search by document type
- [ ] Syntax highlighting for code
- [ ] Export search results
- [ ] Search history
- [ ] Keyboard shortcuts
- [ ] Dark mode

## License

MIT
