import React, { useEffect, useState } from 'react';

interface Event {
  id: number;
  name: string;
  date: string;
}

interface Member {
  id: number;
  name: string;
  voice_part: string;
}

type AttendanceStatus = 'present' | 'absent' | 'late' | 'excused';

interface AttendanceRecord {
  member_id: number;
  status: AttendanceStatus;
}

interface AttendanceRow {
  member: Member;
  status: AttendanceStatus;
}

const STATUS_OPTIONS: { value: AttendanceStatus; label: string; color: string }[] = [
  { value: 'present', label: 'Present', color: 'text-emerald-400' },
  { value: 'absent', label: 'Absent', color: 'text-red-400' },
  { value: 'late', label: 'Late', color: 'text-yellow-400' },
  { value: 'excused', label: 'Excused', color: 'text-blue-400' },
];

const VOICE_PART_ORDER = ['Soprano', 'Alto', 'Tenor', 'Bass', 'Other'];

const API_BASE = '/api';

export default function Attendance() {
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);
  const [attendanceRows, setAttendanceRows] = useState<AttendanceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchEvents();
  }, []);

  useEffect(() => {
    if (selectedEventId !== null) {
      fetchAttendance(selectedEventId);
    } else {
      setAttendanceRows([]);
    }
  }, [selectedEventId]);

  async function fetchEvents() {
    try {
      setError(null);
      const res = await fetch(`${API_BASE}/events`);
      if (!res.ok) throw new Error(`Failed to fetch events: ${res.statusText}`);
      const data: Event[] = await res.json();
      setEvents(data);
      if (data.length > 0) {
        setSelectedEventId(data[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load events');
    }
  }

  async function fetchAttendance(eventId: number) {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await fetch(`${API_BASE}/attendance?event_id=${eventId}`);
      if (!res.ok) throw new Error(`Failed to fetch attendance: ${res.statusText}`);
      const data: { members: Member[]; attendance: AttendanceRecord[] } = await res.json();
      const recordMap = new Map<number, AttendanceStatus>();
      data.attendance.forEach((r) => recordMap.set(r.member_id, r.status));
      const rows: AttendanceRow[] = data.members.map((m) => ({
        member: m,
        status: recordMap.get(m.id) ?? 'present',
      }));
      rows.sort((a, b) => {
        const ai = VOICE_PART_ORDER.indexOf(a.member.voice_part);
        const bi = VOICE_PART_ORDER.indexOf(b.member.voice_part);
        const aIdx = ai === -1 ? VOICE_PART_ORDER.length : ai;
        const bIdx = bi === -1 ? VOICE_PART_ORDER.length : bi;
        if (aIdx !== bIdx) return aIdx - bIdx;
        return a.member.name.localeCompare(b.member.name);
      });
      setAttendanceRows(rows);
    } catch (err: any) {
      setError(err.message || 'Failed to load attendance');
    } finally {
      setLoading(false);
    }
  }

  function handleStatusChange(memberId: number, status: AttendanceStatus) {
    setAttendanceRows((prev) =>
      prev.map((row) =>
        row.member.id === memberId ? { ...row, status } : row
      )
    );
    setSuccessMessage(null);
  }

  async function handleSave() {
    if (selectedEventId === null) return;
    setSaving(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const payload = {
        event_id: selectedEventId,
        records: attendanceRows.map((row) => ({
          member_id: row.member.id,
          status: row.status,
        })),
      };
      const res = await fetch(`${API_BASE}/attendance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Failed to save attendance: ${res.statusText}`);
      setSuccessMessage('Attendance saved successfully!');
    } catch (err: any) {
      setError(err.message || 'Failed to save attendance');
    } finally {
      setSaving(false);
    }
  }

  function setAllStatus(status: AttendanceStatus) {
    setAttendanceRows((prev) => prev.map((row) => ({ ...row, status })));
    setSuccessMessage(null);
  }

  const groupedRows = VOICE_PART_ORDER.reduce<Record<string, AttendanceRow[]>>((acc, part) => {
    const rows = attendanceRows.filter((r) => r.member.voice_part === part);
    if (rows.length > 0) acc[part] = rows;
    return acc;
  }, {});

  const otherRows = attendanceRows.filter(
    (r) => !VOICE_PART_ORDER.slice(0, -1).includes(r.member.voice_part)
  );
  if (otherRows.length > 0) groupedRows['Other'] = otherRows;

  const presentCount = attendanceRows.filter((r) => r.status === 'present').length;
  const absentCount = attendanceRows.filter((r) => r.status === 'absent').length;
  const lateCount = attendanceRows.filter((r) => r.status === 'late').length;
  const excusedCount = attendanceRows.filter((r) => r.status === 'excused').length;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-purple-700 shadow-md">
              <svg className="w-6 h-6 text-purple-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-wide">Attendance</h1>
              <p className="text-sm text-gray-400">Track choir member attendance for each event</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Error / Success */}
        {error && (
          <div className="mb-6 flex items-start gap-3 bg-red-900/40 border border-red-700 rounded-lg px-4 py-3">
            <svg className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        )}
        {successMessage && (
          <div className="mb-6 flex items-start gap-3 bg-emerald-900/40 border border-emerald-700 rounded-lg px-4 py-3">
            <svg className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-emerald-300 text-sm">{successMessage}</p>
          </div>
        )}

        {/* Event Selector */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6 shadow-md">
          <label htmlFor="event-select" className="block text-sm font-semibold text-gray-300 mb-2">
            Select Event
          </label>
          {events.length === 0 ? (
            <p className="text-gray-500 text-sm italic">No events found.</p>
          ) : (
            <select
              id="event-select"
              value={selectedEventId ?? ''}
              onChange={(e) => setSelectedEventId(Number(e.target.value))}
              className="w-full sm:w-96 bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-purple-600 focus:border-transparent transition"
            >
              {events.map((ev) => (
                <option key={ev.id} value={ev.id}>
                  {ev.name} &mdash; {ev.date}
                </option>
              ))}
            </select>
          )}
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
              <span className="text-gray-400 text-sm">Loading attendance...</span>
            </div>
          </div>
        )}

        {!loading && attendanceRows.length > 0 && (
          <>
            {/* Summary Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              {[
                { label: 'Present', count: presentCount, color: 'text-emerald-400', bg: 'bg-emerald-900/30 border-emerald-800' },
                { label: 'Absent', count: absentCount, color: 'text-red-400', bg: 'bg-red-900/30 border-red-800' },
                { label: 'Late', count: lateCount, color: 'text-yellow-400', bg: 'bg-yellow-900/30 border-yellow-800' },
                { label: 'Excused', count: excusedCount, color: 'text-blue-400', bg: 'bg-blue-900/30 border-blue-800' },
              ].map((stat) => (
                <div key={stat.label} className={`rounded-xl border ${stat.bg} px-4 py-4 text-center`}>
                  <p className={`text-3xl font-bold ${stat.color}`}>{stat.count}</p>
                  <p className="text-xs text-gray-400 mt-1 font-medium uppercase tracking-widest">{stat.label}</p>
                </div>
              ))}
            </div>

            {/* Quick-set buttons */}
            <div className="flex flex-wrap gap-2 mb-4">
              <span className="text-sm text-gray-400 self-center mr-1">Mark all as:</span>
              {STATUS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setAllStatus(opt.value)}
                  className="px-3 py-1.5 text-xs font-semibold rounded-md bg-gray-800 border border-gray-700 hover:border-gray-500 hover:bg-gray-700 transition"
                >
                  <span className={opt.color}>{opt.label}</span>
                </button>
              ))}
            </div>

            {/* Attendance Table */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-md mb-6">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-800 border-b border-gray-700">
                      <th className="text-left px-5 py-3.5 font-semibold text-gray-300 w-8">#</th>
                      <th className="text-left px-5 py-3.5 font-semibold text-gray-300">Member Name</th>
                      <th className="text-left px-4 py-3.5 font-semibold text-gray-300">Voice Part</th>
                      {STATUS_OPTIONS.map((opt) => (
                        <th key={opt.value} className="text-center px-3 py-3.5 font-semibold">
                          <span className={`${opt.color} text-xs uppercase tracking-wider`}>{opt.label}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(groupedRows).map(([part, rows]) => (
                      <React.Fragment key={part}>
                        <tr className="bg-gray-850">
                          <td
                            colSpan={6}
                            className="px-5 py-2 text-xs font-bold uppercase tracking-widest text-purple-400 bg-gray-800/60 border-t border-b border-gray-700/60"
                          >
                            {part}
                            <span className="ml-2 font-normal text-gray-500">({rows.length})</span>
                          </td>
                        </tr>
                        {rows.map((row, idx) => {
                          const overallIdx = attendanceRows.indexOf(row) + 1;
                          return (
                            <tr
                              key={row.member.id}
                              className={`border-t border-gray-800 hover:bg-gray-800/50 transition-colors ${
                                idx % 2 === 0 ? 'bg-gray-900' : 'bg-gray-900/70'
                              }`}
                            >
                              <td className="px-5 py-3 text-gray-600 text-xs">{overallIdx}</td>
                              <td className="px-5 py-3">
                                <span className="font-medium text-gray-100">{row.member.name}</span>
                              </td>
                              <td className="px-4 py-3">
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-900/40 text-purple-300 border border-purple-800/50">
                                  {row.member.voice_part}
                                </span>
                              </td>
                              {STATUS_OPTIONS.map((opt) => (
                                <td key={opt.value} className="px-3 py-3 text-center">
                                  <label className="inline-flex items-center justify-center cursor-pointer group">
                                    <input
                                      type="radio"
                                      name={`status-${row.member.id}`}
                                      value={opt.value}
                                      checked={row.status === opt.value}
                                      onChange={() => handleStatusChange(row.member.id, opt.value)}
                                      className="sr-only"
                                    />
                                    <span
                                      className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all ${
                                        row.status === opt.value
                                          ? opt.value === 'present'
                                            ? 'border-emerald-500 bg-emerald-500'
                                            : opt.value === 'absent'
                                            ? 'border-red-500 bg-red-500'
                                            : opt.value === 'late'
                                            ? 'border-yellow-500 bg-yellow-500'
                                            : 'border-blue-500 bg-blue-500'
                                          : 'border-gray-600 bg-transparent group-hover:border-gray-400'
                                      }`}
                                    >
                                      {row.status === opt.value && (
                                        <span className="w-2 h-2 rounded-full bg-white block"></span>
                                      )}
                                    </span>
                                  </label>
                                </td>
                              ))}
                            </tr>
                          );
                        })}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Save Button */}
            <div className="flex justify-end">
              <button
                onClick={handleSave}
                disabled={saving}
                className="inline-flex items-center gap-2 px-8 py-3 bg-purple-700 hover:bg-purple-600 disabled:bg-purple-900 disabled:cursor-not-allowed text-white font-semibold rounded-xl shadow-lg transition-all focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-gray-950"
              >
                {saving ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Save Attendance</span>
                  </>
                )}
              </button>
            </div>
          </>
        )}

        {!loading && selectedEventId !== null && attendanceRows.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <p className="text-gray-400 text-lg font-medium">No members found</p>
            <p className="text-gray-600 text-sm mt-1">No members are associated with this event.</p>
          </div>
        )}
      </main>
    </div>
  );
}
