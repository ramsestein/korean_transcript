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

  // Check if auth is actually required and get available users
  useEffect(() => {
    fetch('/api/auth/status')
      .then(r => r.json())
      .then(data => {
        setAuthEnabled(data.auth_enabled);
        setAvailableUsers(data.users_configured || []);
        if (!data.auth_enabled) {
          onLogin('disabled', 'anonymous');
        }
        setChecking(false);
      })
      .catch(() => {
        setChecking(false);
        setError('Cannot connect to server');
      });
  }, [onLogin]);

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
        setError(data.detail || 'Login failed');
        return;
      }

      onLogin(data.token, data.username);
    } catch (e) {
      setError('Network error. Please try again.');
    }
  };

  if (checking) {
    return (
      <div className="login-container">
        <div className="login-box">
          <div className="spinner" />
          <p>Checking authentication...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>🔒 Korean Meeting Interpreter</h1>
        <p className="login-subtitle">Authentication Required</p>

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
