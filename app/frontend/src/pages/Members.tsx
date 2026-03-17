import React, { useEffect, useState, useCallback } from 'react';

interface Member {
  id: number;
  name: string;
  voice_part: string;
  role: string;
  status: string;
  email?: string;
  phone?: string;
}

const VOICE_PARTS = ['All', 'Soprano', 'Mezzo-Soprano', 'Alto', 'Tenor', 'Baritone', 'Bass'];
const ROLES = ['Singer', 'Section Leader', 'Accompanist', 'Director', 'Assistant Director', 'Admin'];
const STATUSES = ['Active', 'Inactive', 'On Leave', 'Alumni'];

const API_BASE = '/api';

const defaultForm = {
  name: '',
  voice_part: 'Soprano',
  role: 'Singer',
  status: 'Active',
  email: '',
  phone: '',
};

function Badge({ value }: { value: string }) {
  const colorMap: Record<string, string> = {
    Active: 'bg-emerald-900 text-emerald-300 border border-emerald-700',
    Inactive: 'bg-gray-800 text-gray-400 border border-gray-600',
    'On Leave': 'bg-amber-900 text-amber-300 border border-amber-700',
    Alumni: 'bg-purple-900 text-purple-300 border border-purple-700',
    Soprano: 'bg-pink-900 text-pink-300 border border-pink-700',
    'Mezzo-Soprano': 'bg-rose-900 text-rose-300 border border-rose-700',
    Alto: 'bg-orange-900 text-orange-300 border border-orange-700',
    Tenor: 'bg-sky-900 text-sky-300 border border-sky-700',
    Baritone: 'bg-blue-900 text-blue-300 border border-blue-700',
    Bass: 'bg-indigo-900 text-indigo-300 border border-indigo-700',
    Director: 'bg-yellow-900 text-yellow-300 border border-yellow-700',
    'Section Leader': 'bg-teal-900 text-teal-300 border border-teal-700',
    Accompanist: 'bg-violet-900 text-violet-300 border border-violet-700',
  };
  const cls = colorMap[value] || 'bg-gray-800 text-gray-300 border border-gray-600';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
      {value}
    </span>
  );
}

function Modal({
  open,
  onClose,
  children,
  title,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  title: string;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-lg mx-4 bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl shadow-black/60">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <h2 className="text-lg font-bold text-white tracking-wide">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors text-2xl leading-none"
          >
            &times;
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

export default function Members() {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [voiceFilter, setVoiceFilter] = useState('All');
  const [addOpen, setAddOpen] = useState(false);
  const [editMember, setEditMember] = useState<Member | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Member | null>(null);
  const [form, setForm] = useState({ ...defaultForm });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const fetchMembers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/members`);
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setMembers(Array.isArray(data) ? data : data.members ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load members');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchMembers(); }, [fetchMembers]);

  const openAdd = () => {
    setForm({ ...defaultForm });
    setFormError(null);
    setAddOpen(true);
  };

  const openEdit = (m: Member) => {
    setEditMember(m);
    setForm({
      name: m.name,
      voice_part: m.voice_part,
      role: m.role,
      status: m.status,
      email: m.email ?? '',
      phone: m.phone ?? '',
    });
    setFormError(null);
  };

  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setFormError('Name is required.'); return; }
    setSaving(true);
    setFormError(null);
    try {
      const res = await fetch(`${API_BASE}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || `Error ${res.status}`);
      }
      setAddOpen(false);
      await fetchMembers();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Failed to add member');
    } finally {
      setSaving(false);
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editMember) return;
    if (!form.name.trim()) { setFormError('Name is required.'); return; }
    setSaving(true);
    setFormError(null);
    try {
      const res = await fetch(`${API_BASE}/members/${editMember.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || `Error ${res.status}`);
      }
      setEditMember(null);
      await fetchMembers();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Failed to update member');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/members/${deleteTarget.id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      setDeleteTarget(null);
      setDeleteConfirm(false);
      await fetchMembers();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  const filtered = members.filter(m => {
    const matchesSearch =
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.email?.toLowerCase().includes(search.toLowerCase()) ||
      m.role.toLowerCase().includes(search.toLowerCase());
    const matchesVoice = voiceFilter === 'All' || m.voice_part === voiceFilter;
    return matchesSearch && matchesVoice;
  });

  const MemberForm = (
    <form onSubmit={editMember ? handleEditSubmit : handleAddSubmit} className="space-y-4">
      {formError && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-2 text-sm">
          {formError}
        </div>
      )}
      <div className="grid grid-cols-1 gap-4">
        <div>
          <label className="block text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">Full Name *</label>
          <input
            name="name"
            value={form.name}
            onChange={handleFormChange}
            className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition"
            placeholder="Jane Doe"
            autoFocus
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">Voice Part</label>
            <select
              name="voice_part"
              value={form.voice_part}
              onChange={handleFormChange}
              className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition"
            >
              {VOICE_PARTS.filter(v => v !== 'All').map(v => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">Role</label>
            <select
              name="role"
              value={form.role}
              onChange={handleFormChange}
              className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition"
            >
              {ROLES.map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">Status</label>
          <select
            name="status"
            value={form.status}
            onChange={handleFormChange}
            className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition"
          >
            {STATUSES.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">Email</label>
          <input
            name="email"
            type="email"
            value={form.email}
            onChange={handleFormChange}
            className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition"
            placeholder="jane@example.com"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">Phone</label>
          <input
            name="phone"
            type="tel"
            value={form.phone}
            onChange={handleFormChange}
            className="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition"
            placeholder="+1 555 000 0000"
          />
        </div>
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={() => { setAddOpen(false); setEditMember(null); }}
          className="px-4 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-800 transition text-sm font-medium"
          disabled={saving}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving}
          className="px-5 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-sm shadow transition disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {saving ? 'Savingâ¦' : editMember ? 'Save Changes' : 'Add Member'}
        </button>
      </div>
    </form>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <div className="bg-gradient-to-br from-gray-900 via-gray-950 to-black border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <span className="text-3xl">ðµ</span>
                <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-amber-400 to-amber-200 bg-clip-text text-transparent">
                  Choir Members
                </h1>
              </div>
              <p className="text-gray-400 text-sm ml-12">Manage your ensemble roster</p>
            </div>
            <button
              onClick={openAdd}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-semibold text-sm shadow-lg shadow-amber-900/40 transition"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Member
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-5">
        {/* Stats Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Total Members', value: members.length, icon: 'ð¥' },
            { label: 'Active', value: members.filter(m => m.status === 'Active').length, icon: 'â' },
            { label: 'Voice Parts', value: [...new Set(members.map(m => m.voice_part))].length, icon: 'ð¼' },
            { label: 'On Leave', value: members.filter(m => m.status === 'On Leave').length, icon: 'â¸ï¸' },
          ].map(stat => (
            <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-3">
              <span className="text-2xl">{stat.icon}</span>
              <div>
                <div className="text-2xl font-bold text-white">{stat.value}</div>
                <div className="text-xs text-gray-400 font-medium">{stat.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search by name, role, or emailâ¦"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent text-sm transition"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {VOICE_PARTS.map(vp => (
                <button
                  key={vp}
                  onClick={() => setVoiceFilter(vp)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                    voiceFilter === vp
                      ? 'bg-amber-600 border-amber-500 text-white shadow-md shadow-amber-900/40'
                      : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-500 hover:text-white'
                  }`}
                >
                  {vp}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Table / Content */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="flex flex-col items-center gap-4">
                <div className="w-10 h-10 border-4 border-amber-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-gray-400 text-sm">Loading membersâ¦</span>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="text-4xl mb-3">â ï¸</div>
                <p className="text-red-400 font-medium">{error}</p>
                <button onClick={fetchMembers} className="mt-4 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 transition">
                  Retry
                </button>
              </div>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="text-5xl mb-3">ð¶</div>
                <p className="text-gray-400 font-medium">No members found</p>
                <p className="text-gray-600 text-sm mt-1">Try adjusting your filters or add a new member</p>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-800 bg-gray-950/50">
                    <th className="text-left px-5 py-3.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">Member</th>
                    <th className="text-left px-5 py-3.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">Voice Part</th>
                    <th className="text-left px-5 py-3.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">Role</th>
                    <th className="text-left px-5 py-3.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">Status</th>
                    <th className="text-left px-5 py-3.5 text-xs font-semibold text-gray-400 uppercase tracking-wider hidden md:table-cell">Contact</th>
                    <th className="text-right px-5 py-3.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {filtered.map(member => (
                    <tr key={member.id} className="hover:bg-gray-800/40 transition-colors group">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-amber-600 to-amber-800 flex items-center justify-center text-white font-bold text-sm flex-shrink-0 shadow">
                            {member.name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-semibold text-white text-sm">{member.name}</div>
                            <div className="text-xs text-gray-500">{member.email || 'â'}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <Badge value={member.voice_part} />
                      </td>
                      <td className="px-5 py-4">
                        <Badge value={member.role} />
                      </td>
                      <td className="px-5 py-4">
                        <Badge value={member.status} />
                      </td>
                      <td className="px-5 py-4 hidden md:table-cell">
                        <div className="text-sm text-gray-400">{member.phone || 'â'}</div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center justify-end gap-2 opacity-70 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => openEdit(member)}
                            className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-amber-400 transition"
                            title="Edit member"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => { setDeleteTarget(member); setDeleteConfirm(true); }}
                            className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-400 hover:text-red-400 transition"
                            title="Delete member"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {!loading && !error && filtered.length > 0 && (
          <p className="text-xs text-gray-600 text-right">
            Showing {filtered.length} of {members.length} member{members.length !== 1 ? 's' : ''}
          </p>
        )}
      </div>

      {/* Add Member Modal */}
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add New Member">
        {MemberForm}
      </Modal>

      {/* Edit Member Modal */}
      <Modal open={!!editMember} onClose={() => setEditMember(null)} title="Edit Member">
        {MemberForm}
      </Modal>

      {/* Delete Confirm Modal */}
      <Modal open={deleteConfirm} onClose={() => { setDeleteConfirm(false); setDeleteTarget(null); }} title="Remove Member">
        <div className="space-y-5">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-full bg-red-900/40 border border-red-800 flex items-center justify-center flex-shrink-0">
              <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <p className="text-white font-semibold">Remove {deleteTarget?.name}?</p>
              <p className="text-gray-400 text-sm mt-1">
                This will permanently remove <span className="text-white font-medium">{deleteTarget?.name}</span> from the roster. This action cannot be undone.
              </p>
            </div>
          </div>
          <div className="flex justify-end gap-3">
            <button
              onClick={() => { setDeleteConfirm(false); setDeleteTarget(null); }}
              className="px-4 py-2 rounded-lg border border-gray-600 text-gray-300 hover:bg-gray-800 transition text-sm font-medium"
              disabled={saving}
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={saving}
              className="px-5 py-2 rounded-lg bg-red-700 hover:bg-red-600 text-white font-semibold text-sm shadow transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {saving ? 'Removingâ¦' : 'Remove Member'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
