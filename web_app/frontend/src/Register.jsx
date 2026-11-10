import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function Register() {
  const [name, setName] = useState('');
  const [surname, setSurname] = useState('');
  const [age, setAge] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [repeatPassword, setRepeatPassword] = useState('');
  const [statusMessage, setStatusMessage] = useState('');

  const navigate = useNavigate();

  const handleRegister = async (e) => {
    e.preventDefault();

    if (Number(age) < 18) {
      alert('User must be at least 18 years old');
      return;
    }

    if (password !== repeatPassword) {
      alert('Passwords do not match');
      return;
    }

    try {
      const response = await fetch('http://localhost:8080/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          surname,
          age: Number(age),
          email,
          phone,
          password,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Register error:', errorText);

        if (response.status === 409) {
          alert('This email is already registered');
        } else {
          alert('Registration failed. Please check the form.');
        }

        return;
      }

      const registeredUser = await response.json();

      setStatusMessage(`Registered successfully as ${registeredUser.role}`);

      alert('Registration successful. Please login.');

      navigate('/');
    } catch (error) {
      console.error('Register connection error:', error);
      alert('Could not connect to backend server');
    }
  };

  return (
    <div className="register-container">
      <div className="register-wrapper">
        <h2 className="register-greeting">Register</h2>

        <div className="register-box">
          <form className="register-form" onSubmit={handleRegister}>
            <div className="reg-form-groupg">
              <label>Name: </label>
              <input
                type="text"
                placeholder="user-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div className="reg-form-groupg">
              <label>Surname: </label>
              <input
                type="text"
                placeholder="user-surname"
                value={surname}
                onChange={(e) => setSurname(e.target.value)}
                required
              />
            </div>

            <div className="reg-form-groupg">
              <label>Age: </label>
              <input
                type="number"
                placeholder="18"
                value={age}
                onChange={(e) => setAge(e.target.value)}
                required
              />
            </div>

            <div className="reg-form-groupg">
              <label>Email: </label>
              <input
                type="email"
                placeholder="user@user.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="reg-form-groupg">
              <label>Phone: </label>
              <input
                type="tel"
                placeholder="+905350001111"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
              />
            </div>

            <div className="reg-form-groupg">
              <label>Password: </label>
              <input
                type="password"
                placeholder="user123"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="reg-form-groupg">
              <label>Confirm Password: </label>
              <input
                type="password"
                placeholder="user123"
                value={repeatPassword}
                onChange={(e) => setRepeatPassword(e.target.value)}
                required
              />
            </div>

            <br />

            <button type="submit">Register</button>

            {statusMessage && (
              <p style={{ marginTop: '16px', color: '#00754a', fontWeight: 'bold' }}>
                {statusMessage}
              </p>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}

export default Register;