import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createAdminUser,
  deleteAdminUser,
  getAdminUsers,
  updateAdminUserRole,
} from './api';

const EMPTY_FORM = {
  name: '',
  surname: '',
  age: '',
  email: '',
  phone: '',
  password: '',
  role: 'USER',
};

function currentUser() {
  try {
    return JSON.parse(localStorage.getItem('loggedInUser')) || null;
  } catch {
    return null;
  }
}

function ManageUsers() {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [form, setForm] = useState(EMPTY_FORM);
  const [showForm, setShowForm] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const me = currentUser();

  const loadUsers = useCallback(async () => {
    try {
      const data = await getAdminUsers();
      data.sort((a, b) => a.id - b.id);
      setUsers(data);
    } catch (error) {
      console.error('Failed to load users:', error);
      setStatusMessage(`Failed to load users: ${error.message}`);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const visibleUsers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return users.filter((u) => {
      if (roleFilter !== 'ALL' && u.role !== roleFilter) {
        return false;
      }
      if (!q) {
        return true;
      }
      return [u.name, u.surname, u.email, u.phone]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q));
    });
  }, [users, search, roleFilter]);

  const adminCount = users.filter((u) => u.role === 'ADMIN').length;

  const handleRoleChange = async (user, role) => {
    try {
      await updateAdminUserRole(user.id, role);
      setStatusMessage(`${user.name} ${user.surname} is now ${role}.`);
      loadUsers();
    } catch (error) {
      setStatusMessage(`Could not change role: ${error.message}`);
    }
  };

  const handleDelete = async (user) => {
    if (!window.confirm(`Delete ${user.name} ${user.surname} (${user.email})?`)) {
      return;
    }
    try {
      await deleteAdminUser(user.id);
      setStatusMessage(`${user.email} deleted.`);
      loadUsers();
    } catch (error) {
      setStatusMessage(`Could not delete user: ${error.message}`);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      const created = await createAdminUser({
        ...form,
        age: form.age === '' ? null : Number(form.age),
      });
      setStatusMessage(`User ${created.email} created as ${created.role}.`);
      setForm(EMPTY_FORM);
      setShowForm(false);
      loadUsers();
    } catch (error) {
      setStatusMessage(`Could not create user: ${error.message}`);
    }
  };

  const setField = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  return (
    <div className="view-orders-page">
      <h1>Manage Users</h1>
      <p>
        {users.length} users, {adminCount} admin{adminCount === 1 ? '' : 's'}. Search, add users,
        change roles or delete accounts.
      </p>

      <div className="orders-actions users-toolbar">
        <input
          type="text"
          placeholder="Search name, email or phone"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
          <option value="ALL">All roles</option>
          <option value="USER">Users</option>
          <option value="OPERATOR">Operators</option>
          <option value="ADMIN">Admins</option>
        </select>
        <button type="button" onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Close' : 'Add User'}
        </button>
      </div>

      {showForm && (
        <form className="robot-settings-card users-form" onSubmit={handleCreate}>
          <div className="robot-settings-group">
            <label>Name</label>
            <input value={form.name} onChange={setField('name')} required />
          </div>
          <div className="robot-settings-group">
            <label>Surname</label>
            <input value={form.surname} onChange={setField('surname')} required />
          </div>
          <div className="robot-settings-group">
            <label>Age</label>
            <input type="number" min="0" value={form.age} onChange={setField('age')} />
          </div>
          <div className="robot-settings-group">
            <label>Email</label>
            <input type="email" value={form.email} onChange={setField('email')} required />
          </div>
          <div className="robot-settings-group">
            <label>Phone</label>
            <input value={form.phone} onChange={setField('phone')} />
          </div>
          <div className="robot-settings-group">
            <label>Password</label>
            <input
              type="password"
              value={form.password}
              onChange={setField('password')}
              minLength={3}
              required
            />
          </div>
          <div className="robot-settings-group">
            <label>Role</label>
            <select value={form.role} onChange={setField('role')}>
              <option value="USER">USER</option>
              <option value="OPERATOR">OPERATOR</option>
              <option value="ADMIN">ADMIN</option>
            </select>
          </div>
          <div className="robot-settings-actions">
            <button type="submit">Create User</button>
          </div>
        </form>
      )}

      {statusMessage && <p className="robot-settings-status">{statusMessage}</p>}

      {visibleUsers.length === 0 ? (
        <div className="empty-orders-box">
          <h2>No users found</h2>
          <p>{users.length ? 'No user matches the search.' : 'Registered users will appear here.'}</p>
        </div>
      ) : (
        <div className="orders-table-wrapper">
          <table className="orders-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Age</th>
                <th>Role</th>
                <th>Registered</th>
                <th>Delete</th>
              </tr>
            </thead>
            <tbody>
              {visibleUsers.map((user) => {
                const isMe = me && me.id === user.id;
                return (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td>
                      {user.name} {user.surname}
                      {isMe && <strong> (you)</strong>}
                    </td>
                    <td>{user.email}</td>
                    <td>{user.phone || '-'}</td>
                    <td>{user.age ?? '-'}</td>
                    <td>
                      <select
                        value={user.role}
                        onChange={(e) => handleRoleChange(user, e.target.value)}
                      >
                        <option value="USER">USER</option>
                        <option value="OPERATOR">OPERATOR</option>
                        <option value="ADMIN">ADMIN</option>
                      </select>
                    </td>
                    <td>{user.createdAt ? new Date(user.createdAt).toLocaleString() : '-'}</td>
                    <td>
                      <button
                        type="button"
                        className="delete-order-btn"
                        disabled={isMe}
                        title={isMe ? 'You cannot delete your own account' : ''}
                        onClick={() => handleDelete(user)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ManageUsers;
