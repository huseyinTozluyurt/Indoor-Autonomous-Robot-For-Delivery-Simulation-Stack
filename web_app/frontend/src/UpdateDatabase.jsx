import { useEffect, useState } from 'react';
import {
  getAdminUsers,
  createAdminUser,
  updateAdminUserRole,
  deleteAdminUser,
} from './api';

function UpdateDatabase() {
  const [users, setUsers] = useState([]);

  const [name, setName] = useState('');
  const [surname, setSurname] = useState('');
  const [age, setAge] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('USER');

  const [statusMessage, setStatusMessage] = useState('');

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const data = await getAdminUsers();
      setUsers(data);
    } catch (error) {
      console.error('Failed to load users:', error);
      setStatusMessage('Failed to load users from database.');
    }
  };

  const resetForm = () => {
    setName('');
    setSurname('');
    setAge('');
    setEmail('');
    setPhone('');
    setPassword('');
    setRole('USER');
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();

    if (!name.trim() || !surname.trim() || !email.trim() || !password.trim()) {
      alert('Please fill required fields.');
      return;
    }

    try {
      await createAdminUser({
        name,
        surname,
        age: age ? Number(age) : null,
        email,
        phone,
        password,
        role,
      });

      setStatusMessage(`${role} user created successfully.`);
      resetForm();
      await loadUsers();
    } catch (error) {
      console.error('Failed to create user:', error);
      setStatusMessage('Failed to create user. Email may already exist.');
    }
  };

  const handleRoleChange = async (id, newRole) => {
    try {
      await updateAdminUserRole(id, newRole);
      setStatusMessage('User role updated successfully.');
      await loadUsers();
    } catch (error) {
      console.error('Failed to update user role:', error);
      setStatusMessage('Failed to update user role.');
    }
  };

  const handleDeleteUser = async (id, email) => {
    const loggedInUser = JSON.parse(localStorage.getItem('loggedInUser') || '{}');

    if (loggedInUser.email === email) {
      alert('You should not delete your own currently logged-in admin account.');
      return;
    }

    const confirmed = window.confirm(`Delete user ${email}?`);

    if (!confirmed) {
      return;
    }

    try {
      await deleteAdminUser(id);
      setStatusMessage('User deleted successfully.');
      await loadUsers();
    } catch (error) {
      console.error('Failed to delete user:', error);
      setStatusMessage('Failed to delete user.');
    }
  };

  return (
    <div className="update-database-page">
      <h1>User Management</h1>
      <p>Admin can create normal users or additional admin accounts.</p>

      <div className="database-editor-card">
        <h2>Add New User</h2>

        <form className="user-management-form" onSubmit={handleCreateUser}>
          <div className="user-management-grid">
            <div>
              <label>Name</label>
              <input
                type="text"
                placeholder="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div>
              <label>Surname</label>
              <input
                type="text"
                placeholder="Surname"
                value={surname}
                onChange={(e) => setSurname(e.target.value)}
                required
              />
            </div>

            <div>
              <label>Age</label>
              <input
                type="number"
                placeholder="Age"
                value={age}
                onChange={(e) => setAge(e.target.value)}
              />
            </div>

            <div>
              <label>Email</label>
              <input
                type="email"
                placeholder="user@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div>
              <label>Phone</label>
              <input
                type="text"
                placeholder="+905350001111"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>

            <div>
              <label>Password</label>
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div>
              <label>Role</label>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="USER">Normal User</option>
                <option value="ADMIN">Admin User</option>
              </select>
            </div>
          </div>

          <div className="map-actions">
            <button type="submit">Create User</button>
            <button type="button" className="clear-map-btn" onClick={resetForm}>
              Clear Form
            </button>
          </div>
        </form>

        {statusMessage && (
          <p className="robot-settings-status">{statusMessage}</p>
        )}
      </div>

      <div className="saved-maps-section">
        <h2>Existing Users</h2>

        {users.length === 0 ? (
          <div className="empty-database-box">
            <h3>No users found</h3>
            <p>Create users from the form above.</p>
          </div>
        ) : (
          <div className="database-table-wrapper">
            <table className="database-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Surname</th>
                  <th>Age</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>Role</th>
                  <th>Change Role</th>
                  <th>Delete</th>
                </tr>
              </thead>

              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td>{user.name}</td>
                    <td>{user.surname}</td>
                    <td>{user.age || '-'}</td>
                    <td>{user.email}</td>
                    <td>{user.phone || '-'}</td>
                    <td>
                      <strong>{user.role}</strong>
                    </td>
                    <td>
                      <select
                        value={user.role}
                        onChange={(e) => handleRoleChange(user.id, e.target.value)}
                      >
                        <option value="USER">USER</option>
                        <option value="ADMIN">ADMIN</option>
                      </select>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="delete-table-btn"
                        onClick={() => handleDeleteUser(user.id, user.email)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default UpdateDatabase;