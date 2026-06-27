import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';

function Home() {
  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>Ryo Nagaki-DiLazzaro</h1>
      <h2>Software Developer</h2>
      <ul>
        <li><a href="https://mcb.ryo-nd.com">Most Common Blunder (Chess Analyzer)</a></li>
        <li><Link to="/spam-shredder/privacy">Spam Shredder Privacy Policy</Link></li>
      </ul>
    </div>
  );
}

function PrivacyPolicy() {
  return (
    <div style={{ padding: '2rem', maxWidth: '800px', fontFamily: 'sans-serif' }}>
      <Link to="/">← Back to Portfolio</Link>
      <h1>Privacy Policy for Spam Shredder</h1>
      <p>Last updated: June 27, 2026</p>
      <p>Your simple text goes here...</p>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/spam-shredder/privacy" element={<PrivacyPolicy />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;