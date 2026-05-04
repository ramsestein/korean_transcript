import { useState, useEffect } from 'react';

type Props = {
  onLogin: (token: string) => void;
};

export function Login({ onLogin }: Props) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [checking, setChecking] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(true);

  // Check if auth is actually required
  useEffect(() => {
    fetch('/api/auth/status')
      .then(r => r.json())
      .then(data => {
        setAuthEnabled(data.auth_enabled);
        if (!data.auth_enabled) {
          onLogin('disabled');
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
        body: JSON.stringify({ password }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || 'Login failed');
        return;
      }

      onLogin(data.token);
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

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter admin password"
              autoFocus
            />
          </div>

          {error && (
            <div className="error-banner">
              {error}
            </div>
          )}

          <button type="submit" className="btn-primary" disabled={!password}>
            Login
          </button>
        </form>
      </div>
    </div>
  );
}
