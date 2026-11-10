import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';

function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();


  const handleLogin = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch('http://localhost:8080/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
        }),
      });

      if (!response.ok) {
        alert('Invalid email or password');
        return;
      }

      const user = await response.json();

      localStorage.setItem('loggedInUser', JSON.stringify(user));

      window.dispatchEvent(new Event('deliverybot-login'));

      if (user.role === 'ADMIN') {
        navigate('/admin');
      } else if (user.role === 'OPERATOR') {
        navigate('/operator');
      } else {
        navigate('/main');
      }
    } catch (error) {
      console.error('Login error:', error);
      alert('Could not connect to backend server');
    }
  };


  return (
    <div className="login-container">
      <div className="login-greeting">
        <h2>Welcome to Starbucks</h2>
      </div>
      <div className="login-wrapper">
        <div className="login-box">
          <h2>Login</h2>
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>Email:</label>
              <input type="email" placeholder='example@example.com' value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="form-group">
              <label>Password:</label>
              <input type="password" placeholder='example123.' value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            Don't have an account? <Link to="/register">Register</Link><br /><br />
            <button type="submit">Login</button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
