import React, { useState, useEffect, useCallback } from 'react';

interface Event {
  id: string;
  title: string;
  date: string;
  venue: string;
  type: 'rehearsal' | 'performance' | 'other';
  setlist?: SetlistItem[];
  description?: string;
}

interface SetlistItem {
  id: string;
  order: number;
  title: string;
  composer: string;
  duration?: string;
}

interface CreateEventForm {
  title: string;
  date: string;
  venue: string;
  type: 'rehearsal' | 'performance' | 'other';
  description: string;
}

const API_BASE = '/api';

const typeColors: Record<string, string> = {
  rehearsal: 'bg-indigo-900/60 text-indigo-300 border-indigo-700',
  performance: 'bg-amber-900/60 text-amber-300 border-amber-700',
  other: 'bg-slate-700/60 text-slate-300 border-slate-600',
};

const typeLabels: Record<string, string> = {
  rehearsal: 'Rehearsal',
  performance: 'Performance',
  other: 'Other',
};

const typeBadgeColors: Record<string, string> = {
  rehearsal: 'bg-indigo-700 text-indigo-100',
  performance: 'bg-amber-700 text-amber-100',
  other: 'bg-slate-600 text-slate-100',
};

export default function Events() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [filterType, setFilterType] = useState<string>('all');
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [form, setForm] = useState<CreateEventForm>({
    title: '',
    date: '',
    venue: '',
    type: 'rehearsal',
    description: '',
  });

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/events`);
      if (!res.ok) throw new Error('Failed to fetch events');
      const data = await res.json();
      setEvents(data);
    } catch (e: any) {
      setError(e.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const fetchEventDetail = async (id: string) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/events/${id}`);
      if (!res.ok) throw new Error('Failed to fetch event details');
      const data = await res.json();
      setSelectedEvent(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateLoading(true);
    setCreateError(null);
    try {
      const res = await fetch(`${API_BASE}/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error('Failed to create event');
      await fetchEvents();
      setShowCreateModal(false);
      setForm({ title: '', date: '', venue: '', type: 'rehearsal', description: '' });
    } catch (e: any) {
      setCreateError(e.message || 'Failed to create event');
    } finally {
      setCreateLoading(false);
    }
  };

  const filteredEvents = events.filter(ev => filterType === 'all' || ev.type === filterType);

  const sortedEvents = [...filteredEvents].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  const upcomingEvents = sortedEvents.filter(ev => new Date(ev.date) >= new Date());
  const pastEvents = sortedEvents.filter(ev => new Date(ev.date) < new Date());

  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    return { firstDay, daysInMonth, year, month };
  };

  const getEventsForDay = (day: number, month: number, year: number) => {
    return filteredEvents.filter(ev => {
      const d = new Date(ev.date);
      return d.getDate() === day && d.getMonth() === month && d.getFullYear() === year;
    });
  };

  const { firstDay, daysInMonth, year, month } = getDaysInMonth(currentMonth);
  const today = new Date();

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  };

  const formatTime = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <div className="bg-gradient-to-b from-gray-900 to-gray-950 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-500 to-amber-700 flex items-center justify-center">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h1 className="text-2xl font-bold text-white tracking-wide">Events</h1>
              </div>
              <p className="text-gray-400 text-sm">Manage rehearsals, performances, and choir events</p>
            </div>
            <div className="flex items-center gap-3">
              {/* Filter */}
              <select
                value={filterType}
                onChange={e => setFilterType(e.target.value)}
                className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-amber-500"
              >
                <option value="all">All Types</option>
                <option value="rehearsal">Rehearsals</option>
                <option value="performance">Performances</option>
                <option value="other">Other</option>
              </select>
              {/* View Toggle */}
              <div className="flex bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
                <button
                  onClick={() => setViewMode('list')}
                  className={`px-3 py-2 text-sm font-medium transition-colors ${
                    viewMode === 'list'
                      ? 'bg-amber-600 text-white'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                  </svg>
                </button>
                <button
                  onClick={() => setViewMode('calendar')}
                  className={`px-3 py-2 text-sm font-medium transition-colors ${
                    viewMode === 'calendar'
                      ? 'bg-amber-600 text-white'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </button>
              </div>
              <button
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-2 bg-amber-600 hover:bg-amber-500 text-white font-semibold px-4 py-2 rounded-lg transition-colors text-sm shadow-lg shadow-amber-900/30"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New Event
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-24">
            <div className="text-center">
              <div className="w-12 h-12 border-4 border-amber-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-gray-400">Loading events...</p>
            </div>
          </div>
        ) : viewMode === 'list' ? (
          <div className="space-y-8">
            {/* Upcoming */}
            <div>
              <h2 className="text-lg font-semibold text-gray-200 mb-4 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
                Upcoming Events
                <span className="text-sm font-normal text-gray-500">({upcomingEvents.length})</span>
              </h2>
              {upcomingEvents.length === 0 ? (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
                  <div className="w-12 h-12 bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <p className="text-gray-500">No upcoming events scheduled</p>
                  <button
                    onClick={() => setShowCreateModal(true)}
                    className="mt-3 text-amber-400 hover:text-amber-300 text-sm underline"
                  >
                    Create your first event
                  </button>
                </div>
              ) : (
                <div className="grid gap-4">
                  {upcomingEvents.map(ev => (
                    <EventCard key={ev.id} event={ev} onClick={() => fetchEventDetail(ev.id)} />
                  ))}
                </div>
              )}
            </div>

            {/* Past */}
            {pastEvents.length > 0 && (
              <div>
                <h2 className="text-lg font-semibold text-gray-400 mb-4 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-gray-600 inline-block" />
                  Past Events
                  <span className="text-sm font-normal text-gray-600">({pastEvents.length})</span>
                </h2>
                <div className="grid gap-4 opacity-60">
                  {pastEvents.slice().reverse().map(ev => (
                    <EventCard key={ev.id} event={ev} onClick={() => fetchEventDetail(ev.id)} past />
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Calendar View */
          <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
            {/* Calendar Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <button
                onClick={() => setCurrentMonth(new Date(year, month - 1, 1))}
                className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-gray-200 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <h2 className="text-lg font-bold text-white">
                {monthNames[month]} {year}
              </h2>
              <button
                onClick={() => setCurrentMonth(new Date(year, month + 1, 1))}
                className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-gray-200 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>

            {/* Day Headers */}
            <div className="grid grid-cols-7 border-b border-gray-800">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
                <div key={d} className="py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  {d}
                </div>
              ))}
            </div>

            {/* Calendar Grid */}
            <div className="grid grid-cols-7">
              {Array.from({ length: firstDay }).map((_, i) => (
                <div key={`empty-${i}`} className="min-h-24 border-r border-b border-gray-800/50 bg-gray-950/30" />
              ))}
              {Array.from({ length: daysInMonth }).map((_, i) => {
                const day = i + 1;
                const dayEvents = getEventsForDay(day, month, year);
                const isToday =
                  today.getDate() === day &&
                  today.getMonth() === month &&
                  today.getFullYear() === year;
                return (
                  <div
                    key={day}
                    className={`min-h-24 border-r border-b border-gray-800/50 p-2 ${
                      isToday ? 'bg-amber-950/20' : 'hover:bg-gray-800/30'
                    } transition-colors`}
                  >
                    <div
                      className={`text-sm font-medium mb-1 w-7 h-7 flex items-center justify-center rounded-full ${
                        isToday
                          ? 'bg-amber-600 text-white'
                          : 'text-gray-400'
                      }`}
                    >
                      {day}
                    </div>
                    <div className="space-y-1">
                      {dayEvents.map(ev => (
                        <button
                          key={ev.id}
                          onClick={() => fetchEventDetail(ev.id)}
                          className={`w-full text-left text-xs px-1.5 py-0.5 rounded font-medium truncate ${
                            ev.type === 'performance'
                              ? 'bg-amber-800/60 text-amber-200 hover:bg-amber-700/60'
                              : ev.type === 'rehearsal'
                              ? 'bg-indigo-800/60 text-indigo-200 hover:bg-indigo-700/60'
                              : 'bg-gray-700/60 text-gray-200 hover:bg-gray-600/60'
                          } transition-colors`}
                        >
                          {ev.title}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Legend */}
            <div className="flex items-center gap-6 px-6 py-4 border-t border-gray-800">
              {['rehearsal', 'performance', 'other'].map(t => (
                <div key={t} className="flex items-center gap-2">
                  <span
                    className={`w-3 h-3 rounded-sm ${
                      t === 'performance' ? 'bg-amber-700' : t === 'rehearsal' ? 'bg-indigo-700' : 'bg-gray-600'
                    }`}
                  />
                  <span className="text-xs text-gray-400 capitalize">{t}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Create Event Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="flex items-center justify-between px-6 py-5 border-b border-gray-800">
              <div>
                <h2 className="text-lg font-bold text-white">Create New Event</h2>
                <p className="text-gray-400 text-sm">Add a rehearsal, performance, or other event</p>
              </div>
              <button
                onClick={() => { setShowCreateModal(false); setCreateError(null); }}
                className="text-gray-500 hover:text-gray-300 transition-colors p-1"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleCreateEvent} className="px-6 py-5 space-y-4">
              {createError && (
                <div className="p-3 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">
                  {createError}
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Event Title *</label>
                <input
                  type="text"
                  required
                  value={form.title}
                  onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="e.g. Spring Concert Rehearsal"
                  className="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent placeholder-gray-600"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Date & Time *</label>
                  <input
                    type="datetime-local"
                    required
                    value={form.date}
                    onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Event Type *</label>
                  <select
                    required
                    value={form.type}
                    onChange={e => setForm(f => ({ ...f, type: e.target.value as any }))}
                    className="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  >
                    <option value="rehearsal">Rehearsal</option>
                    <option value="performance">Performance</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Venue</label>
                <input
                  type="text"
                  value={form.venue}
                  onChange={e => setForm(f => ({ ...f, venue: e.target.value }))}
                  placeholder="e.g. Main Hall, St. Mary's Church"
                  className="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent placeholder-gray-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Description</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Additional notes or instructions..."
                  rows={3}
                  className="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent placeholder-gray-600 resize-none"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => { setShowCreateModal(false); setCreateError(null); }}
                  className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium py-2.5 rounded-lg transition-colors text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="flex-1 bg-amber-600 hover:bg-amber-500 disabled:bg-amber-800 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-lg transition-colors text-sm flex items-center justify-center gap-2"
                >
                  {createLoading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Creating...
                    </>
                  ) : 'Create Event'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Event Detail Modal */}
      {(selectedEvent || detailLoading) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
            {detailLoading ? (
              <div className="flex items-center justify-center py-24">
                <div className="text-center">
                  <div className="w-10 h-10 border-4 border-amber-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                  <p className="text-gray-400 text-sm">Loading event details...</p>
                </div>
              </div>
            ) : selectedEvent ? (
              <>
                {/* Detail Header */}
                <div
                  className={`px-6 py-5 border-b border-gray-800 ${
                    selectedEvent.type === 'performance'
                      ? 'bg-gradient-to-r from-amber-950/50 to-gray-900'
                      : selectedEvent.type === 'rehearsal'
                      ? 'bg-gradient-to-r from-indigo-950/50 to-gray-900'
                      : 'bg-gray-900'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        <span
                          className={`text-xs font-semibold px-2.5 py-1 rounded-full uppercase tracking-wider ${
                            typeBadgeColors[selectedEvent.type]
                          }`}
                        >
                          {typeLabels[selectedEvent.type]}
                        </span>
                      </div>
                      <h2 className="text-xl font-bold text-white mb-1">{selectedEvent.title}</h2>
                      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-sm text-gray-400">
                        <span className="flex items-center gap-1.5">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                          {formatDate(selectedEvent.date)}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          {formatTime(selectedEvent.date)}
                        </span>
                        {selectedEvent.venue && (
                          <span className="flex items-center gap-1.5">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            {selectedEvent.venue}
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedEvent(null)}
                      className="text-gray-500 hover:text-gray-300 transition-colors p-1 mt-1"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>

                <div className="overflow-y-auto flex-1 px-6 py-5 space-y-6">
                  {/* Description */}
                  {selectedEvent.description && (
                    <div>
                      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">Description</h3>
                      <p className="text-gray-300 text-sm leading-relaxed bg-gray-800/40 rounded-lg p-4">
                        {selectedEvent.description}
                      </p>
                    </div>
                  )}

                  {/* Setlist */}
                  {selectedEvent.setlist && selectedEvent.setlist.length > 0 ? (
                    <div>
                      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                        </svg>
                        Setlist
                        <span className="bg-gray-700 text-gray-300 text-xs px-2 py-0.5 rounded-full">
                          {selectedEvent.setlist.length} pieces
                        </span>
                      </h3>
                      <div className="space-y-2">
                        {[...selectedEvent.setlist]
                          .sort((a, b) => a.order - b.order)
                          .map((item, idx) => (
                            <div
                              key={item.id}
                              className="flex items-center gap-4 bg-gray-800/60 border border-gray-700/50 rounded-lg px-4 py-3 hover:bg-gray-800 transition-colors"
                            >
                              <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-400 flex-shrink-0">
                                {idx + 1}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-gray-100 font-medium text-sm truncate">{item.title}</p>
                                <p className="text-gray-500 text-xs">{item.composer}</p>
                              </div>
                              {item.duration && (
                                <span className="text-gray-500 text-xs flex-shrink-0">{item.duration}</span>
                              )}
                            </div>
                          ))}
                      </div>
                    </div>
                  ) : (
                    <div className="bg-gray-800/30 border border-gray-700/50 rounded-xl p-6 text-center">
                      <div className="w-10 h-10 bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-2">
                        <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                        </svg>
                      </div>
                      <p className="text-gray-500 text-sm">No setlist assigned to this event</p>
                    </div>
                  )}
                </div>

                <div className="px-6 py-4 border-t border-gray-800 flex justify-end">
                  <button
                    onClick={() => setSelectedEvent(null)}
                    className="bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium px-6 py-2 rounded-lg transition-colors text-sm"
                  >
                    Close
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}

function EventCard({
  event,
  onClick,
  past = false,
}: {
  event: Event;
  onClick: () => void;
  past?: boolean;
}) {
  const d = new Date(event.date);
  const dayNum = d.getDate();
  const monthShort = d.toLocaleString('en-US', { month: 'short' });
  const timeStr = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

  return (
    <button
      onClick={onClick}
      className={`w-full text-left bg-gray-900 border rounded-xl p-5 hover:border-gray-600 transition-all group ${
        past ? 'border-gray-800' : 'border-gray-700 hover:shadow-lg hover:shadow-black/30'
      }`}
    >
      <div className="flex items-start gap-4">
        {/* Date Badge */}
        <div
          className={`flex-shrink-0 w-14 h-14 rounded-xl flex flex-col items-center justify-center border ${
            typeColors[event.type]
          }`}
        >
          <span className="text-xs font-semibold uppercase tracking-wider opacity-80">{monthShort}</span>
          <span className="text-xl font-bold leading-none">{dayNum}</span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h3 className="font-semibold text-white group-hover:text-amber-300 transition-colors text-base leading-tight">
                {event.title}
              </h3>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5">
                <span className="text-gray-400 text-sm flex items-center gap-1">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {timeStr}
                </span>
                {event.venue && (
                  <span className="text-gray-400 text-sm flex items-center gap-1">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    {event.venue}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                  event.type === 'performance'
                    ? 'bg-amber-900/60 text-amber-300'
                    : event.type === 'rehearsal'
                    ? 'bg-indigo-900/60 text-indigo-300'
                    : 'bg-gray-700/60 text-gray-300'
                }`}
              >
                {event.type.charAt(0).toUpperCase() + event.type.slice(1)}
              </span>
              <svg
                className="w-4 h-4 text-gray-600 group-hover:text-amber-400 transition-colors"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </button>
  );
}
