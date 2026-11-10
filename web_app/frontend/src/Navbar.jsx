import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { getLoggedInUser } from './api';

function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(getLoggedInUser());

  // refresh after login / logout and on every page change
  useEffect(() => {
    setUser(getLoggedInUser());
  }, [location.pathname]);

  useEffect(() => {
    const update = () => setUser(getLoggedInUser());
    window.addEventListener('deliverybot-login', update);
    window.addEventListener('storage', update);
    return () => {
      window.removeEventListener('deliverybot-login', update);
      window.removeEventListener('storage', update);
    };
  }, []);

  const logout = () => {
    localStorage.removeItem('loggedInUser');
    setUser(null);
    navigate('/');
  };

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <Link to={user ? (user.role === 'ADMIN' ? '/admin' : user.role === 'OPERATOR' ? '/operator' : '/main') : '/'}
              className="navbar-logo">
          DeliveryBot
        </Link>
      </div>

      <div className="navbar-menu">
        {!user && (
          <Link to="/" className="navbar-link">
            Home Page
          </Link>
        )}

        {user && (
          <Link to="/main" className="navbar-link">
            Order
          </Link>
        )}

        {user && ['OPERATOR', 'ADMIN'].includes(user.role) && (
          <Link to="/operator" className="navbar-link">
            Operator
          </Link>
        )}

        {user && user.role === 'ADMIN' && (
          <Link to="/admin" className="navbar-link">
            Admin
          </Link>
        )}

        <Link to="/products" className="navbar-link">
          Products
        </Link>

        <Link to="/about" className="navbar-link">
          About Us
        </Link>

        {user && (
          <>
            <span className="navbar-user">
              {user.name} <small>({user.role.toLowerCase()})</small>
            </span>
            <button type="button" className="navbar-logout" onClick={logout}>
              Log out
            </button>
          </>
        )}
      </div>
    </nav>
  );
}

export default Navbar;
