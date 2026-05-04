import { useState, useEffect } from 'react';

type Props = {
  onLogin: (token: string, username: string) => void;
};

export function Login({ onLogin }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [checking, setChecking] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(true);
  const [availableUsers, setAvailableUsers] = useState<string[]>([]);

  // Check auth status once on mount
  useEffect(() => {
    console.log('Login: checking auth status...');
    fetch('/api/auth/status')
      .then(r => {
        console.log('Login: auth status response', r.status);
        return r.json();
      })
      .then(data => {
        console.log('Login: auth data', data);
        setAuthEnabled(data.auth_enabled);
        setAvailableUsers(data.users_configured || []);
        setChecking(false);
        // Only auto-login if auth is disabled
        if (!data.auth_enabled) {
          console.log('Login: auth disabled, auto-logging in');
          onLogin('disabled', 'anonymous');
        }
      })
      .catch((err) => {
        console.error('Login: error fetching auth status', err);
        setChecking(false);
        setError('Cannot connect to server');
      });
    // Empty deps = run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        // Handle both string and object error details
        const errorMsg = typeof data.detail === 'string' 
          ? data.detail 
          : data.detail?.msg || JSON.stringify(data.detail) || 'Login failed';
        setError(errorMsg);
        return;
      }

      onLogin(data.token, data.username);
    } catch (e) {
      setError('Network error. Please try again.');
    }
  };

  if (checking) {
    return (
      <div className="login-container" style={{ background: '#0f172a', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="login-box" style={{ color: 'white', textAlign: 'center' }}>
          <div className="spinner" />
          <p>Checking authentication...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-container" style={{ background: '#0f172a', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="login-box" style={{ background: '#1e293b', padding: '32px', borderRadius: '12px', color: 'white', maxWidth: '360px', width: '90%' }}>
        <h1 style={{ margin: '0 0 8px', fontSize: '1.5rem' }}>🔒 Korean Meeting Interpreter</h1>
        <p className="login-subtitle" style={{ color: '#94a3b8', marginBottom: '24px' }}>Authentication Required</p>

        {availableUsers.length > 0 && (
          <div className="users-hint">
            <small>Available users: {availableUsers.join(', ')}</small>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
            />
          </div>

          {error && (
            <div className="error-banner">
              {error}
            </div>
          )}

          <button type="submit" className="btn-primary" disabled={!username || !password}>
            Login
          </button>
        </form>
      </div>
    </div>
  );
}
