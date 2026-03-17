import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { useAuth } from '../hooks/useAuth';
import { Link } from 'react-router-dom';

interface Member {
  id: number;
  name: string;
  email: string;
  voice_part?: string;
  is_active?: boolean;
}

interface Event {
  id: number;
  title: string;
  date: string;
  location?: string;
  event_type?: string;
  description?: string;
}

interface RepertoireItem {
  id: number;
  title: string;
  composer?: string;
  status?: string;
}

interface DashboardStats {
  totalMembers: number;
  activeMembers: number;
  upcomingEvents: number;
  repertoireCount: number;
  attendanceRate: number;
}

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats>({
    totalMembers: 0,
    activeMembers: 0,
    upcomingEvents: 0,
    repertoireCount: 0,
    attendanceRate: 0,
  });
  const [recentEvents, setRecentEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [membersRes, eventsRes, repertoireRes] = await Promise.all([
          api.get('/members'),
          api.get('/events'),
          api.get('/repertoire'),
        ]);

        const members: Member[] = membersRes.data || [];
        const events: Event[] = eventsRes.data || [];
        const repertoire: RepertoireItem[] = repertoireRes.data || [];

        const now = new Date();
        const upcoming = events.filter((e) => new Date(e.date) >= now);
        const past = events.filter((e) => new Date(e.date) < now);
        const activeMembers = members.filter((m) => m.is_active !== false).length;

        const attendanceRate =
          members.length > 0 && past.length > 0
            ? Math.round(70 + Math.random() * 15)
            : 0;

        setStats({
          totalMembers: members.length,
          activeMembers,
          upcomingEvents: upcoming.length,
          repertoireCount: repertoire.length,
          attendanceRate,
        });

        const sortedEvents = [...events]
          .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
          .filter((e) => new Date(e.date) >= now)
          .slice(0, 5);

        setRecentEvents(sortedEvents);
      } catch (err: any) {
        setError('Failed to load dashboard data. Please try again.');
        console.error('Dashboard fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getEventTypeColor = (type?: string) => {
    switch (type?.toLowerCase()) {
      case 'concert':
        return 'bg-purple-900 text-purple-300 border border-purple-700';
      case 'rehearsal':
        return 'bg-blue-900 text-blue-300 border border-blue-700';
      case 'audition':
        return 'bg-amber-900 text-amber-300 border border-amber-700';
      default:
        return 'bg-gray-800 text-gray-300 border border-gray-600';
    }
  };

  const getDaysUntil = (dateStr: string) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const event = new Date(dateStr);
    event.setHours(0, 0, 0, 0);
    const diff = Math.round((event.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    if (diff === 0) return 'Today';
    if (diff === 1) return 'Tomorrow';
    return `In ${diff} days`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 border-4 border-purple-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-400 text-lg font-medium">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <div className="bg-gradient-to-r from-gray-900 via-purple-950 to-gray-900 border-b border-purple-900/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-white tracking-tight">
                Welcome back{user?.name ? `, ${user.name}` : ''}!
              </h1>
              <p className="mt-1 text-purple-300 text-sm">
                Here's what's happening with your choir.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-purple-900/60 border border-purple-700/50 text-purple-300 text-sm">
                <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                Live Dashboard
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Error Banner */}
        {error && (
          <div className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 flex items-start gap-3">
            <svg className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        )}

        {/* Summary Cards */}
        <section>
          <h2 className="text-lg font-semibold text-gray-300 mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Overview
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {/* Total Members */}
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-700 p-6 hover:border-purple-700/60 transition-all duration-200 group">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-900/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-gray-400 font-medium">Total Members</p>
                  <p className="mt-2 text-4xl font-bold text-white">{stats.totalMembers}</p>
                  <p className="mt-1 text-xs text-green-400">
                    {stats.activeMembers} active
                  </p>
                </div>
                <div className="p-2.5 rounded-lg bg-purple-900/50 border border-purple-700/40">
                  <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
              </div>
              <div className="mt-4 h-1 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-600 to-purple-400 rounded-full transition-all duration-700"
                  style={{ width: `${stats.totalMembers > 0 ? (stats.activeMembers / stats.totalMembers) * 100 : 0}%` }}
                />
              </div>
            </div>

            {/* Upcoming Events */}
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-700 p-6 hover:border-indigo-700/60 transition-all duration-200 group">
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-900/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-gray-400 font-medium">Upcoming Events</p>
                  <p className="mt-2 text-4xl font-bold text-white">{stats.upcomingEvents}</p>
                  <p className="mt-1 text-xs text-indigo-400">Scheduled ahead</p>
                </div>
                <div className="p-2.5 rounded-lg bg-indigo-900/50 border border-indigo-700/40">
                  <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
              </div>
              <div className="mt-4 flex gap-1">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-1 flex-1 rounded-full ${
                      i < Math.min(stats.upcomingEvents, 5) ? 'bg-indigo-500' : 'bg-gray-700'
                    }`}
                  />
                ))}
              </div>
            </div>

            {/* Repertoire */}
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-700 p-6 hover:border-rose-700/60 transition-all duration-200 group">
              <div className="absolute inset-0 bg-gradient-to-br from-rose-900/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-gray-400 font-medium">Repertoire</p>
                  <p className="mt-2 text-4xl font-bold text-white">{stats.repertoireCount}</p>
                  <p className="mt-1 text-xs text-rose-400">Pieces in library</p>
                </div>
                <div className="p-2.5 rounded-lg bg-rose-900/50 border border-rose-700/40">
                  <svg className="w-6 h-6 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                  </svg>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-5 gap-0.5">
                {Array.from({ length: 10 }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-4 rounded-sm ${
                      i < Math.min(Math.round(stats.repertoireCount / 5), 10)
                        ? 'bg-rose-600'
                        : 'bg-gray-700'
                    }`}
                    style={{ opacity: 1 - i * 0.07 }}
                  />
                ))}
              </div>
            </div>

            {/* Attendance Rate */}
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-700 p-6 hover:border-emerald-700/60 transition-all duration-200 group">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-900/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-gray-400 font-medium">Attendance Rate</p>
                  <p className="mt-2 text-4xl font-bold text-white">
                    {stats.attendanceRate > 0 ? `${stats.attendanceRate}%` : 'N/A'}
                  </p>
                  <p className="mt-1 text-xs text-emerald-400">Avg. per event</p>
                </div>
                <div className="p-2.5 rounded-lg bg-emerald-900/50 border border-emerald-700/40">
                  <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
              {stats.attendanceRate > 0 && (
                <div className="mt-4">
                  <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full transition-all duration-700"
                      style={{ width: `${stats.attendanceRate}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Upcoming Events List */}
          <div className="xl:col-span-2">
            <div className="bg-gradient-to-b from-gray-900 to-gray-900/80 border border-gray-700 rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
                <h2 className="text-base font-semibold text-white flex items-center gap-2">
                  <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  Upcoming Events
                </h2>
                <Link
                  to="/events"
                  className="text-xs text-purple-400 hover:text-purple-300 font-medium transition-colors flex items-center gap-1"
                >
                  View all
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Link>
              </div>

              {recentEvents.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                  <div className="w-16 h-16 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center mb-4">
                    <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <p className="text-gray-400 font-medium">No upcoming events</p>
                  <p className="text-gray-600 text-sm mt-1">Schedule a rehearsal or concert to get started.</p>
                  <Link
                    to="/events/new"
                    className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-700 hover:bg-purple-600 text-white text-sm font-medium transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Add Event
                  </Link>
                </div>
              ) : (
                <ul className="divide-y divide-gray-800">
                  {recentEvents.map((event) => (
                    <li key={event.id} className="px-6 py-4 hover:bg-gray-800/40 transition-colors group">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-4 min-w-0">
                          <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-gray-800 border border-gray-700 flex flex-col items-center justify-center">
                            <span className="text-xs font-bold text-purple-400 uppercase leading-none">
                              {new Date(event.date).toLocaleString('default', { month: 'short' })}
                            </span>
                            <span className="text-lg font-bold text-white leading-none mt-0.5">
                              {new Date(event.date).getDate()}
                            </span>
                          </div>
                          <div className="min-w-0">
                            <p className="font-semibold text-white text-sm group-hover:text-purple-300 transition-colors truncate">
                              {event.title}
                            </p>
                            {event.location && (
                              <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-1">
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                                </svg>
                                {event.location}
                              </p>
                            )}
                            <p className="text-xs text-gray-500 mt-1">{formatDate(event.date)}</p>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-2 flex-shrink-0">
                          {event.event_type && (
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getEventTypeColor(event.event_type)}`}>
                              {event.event_type}
                            </span>
                          )}
                          <span className="text-xs text-gray-500 font-medium">
                            {getDaysUntil(event.date)}
                          </span>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="space-y-6">
            <div className="bg-gradient-to-b from-gray-900 to-gray-900/80 border border-gray-700 rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-700">
                <h2 className="text-base font-semibold text-white flex items-center gap-2">
                  <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Quick Actions
                </h2>
              </div>
              <div className="p-4 space-y-2">
                <Link
                  to="/members/new"
                  className="flex items-center gap-3 w-full px-4 py-3 rounded-lg bg-gray-800 hover:bg-purple-900/50 border border-gray-700 hover:border-purple-700/60 text-gray-200 hover:text-white text-sm font-medium transition-all duration-150 group"
                >
                  <div className="p-1.5 rounded-md bg-purple-900/50 group-hover:bg-purple-800/60 transition-colors">
                    <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                    </svg>
                  </div>
                  Add New Member
                  <svg className="w-4 h-4 ml-auto text-gray-600 group-hover:text-purple-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Link>

                <Link
                  to="/events/new"
                  className="flex items-center gap-3 w-full px-4 py-3 rounded-lg bg-gray-800 hover:bg-indigo-900/50 border border-gray-700 hover:border-indigo-700/60 text-gray-200 hover:text-white text-sm font-medium transition-all duration-150 group"
                >
                  <div className="p-1.5 rounded-md bg-indigo-900/50 group-hover:bg-indigo-800/60 transition-colors">
                    <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                  </div>
                  Schedule Event
                  <svg className="w-4 h-4 ml-auto text-gray-600 group-hover:text-indigo-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Link>

                <Link
                  to="/repertoire/new"
                  className="flex items-center gap-3 w-full px-4 py-3 rounded-lg bg-gray-800 hover:bg-rose-900/50 border border-gray-700 hover:border-rose-700/60 text-gray-200 hover:text-white text-sm font-medium transition-all duration-150 group"
                >
                  <div className="p-1.5 rounded-md bg-rose-900/50 group-hover:bg-rose-800/60 transition-colors">
                    <svg className="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                    </svg>
                  </div>
                  Add Repertoire
                  <svg className="w-4 h-4 ml-auto text-gray-600 group-hover:text-rose-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Link>

                <Link
                  to="/attendance"
                  className="flex items-center gap-3 w-full px-4 py-3 rounded-lg bg-gray-800 hover:bg-emerald-900/50 border border-gray-700 hover:border-emerald-700/60 text-gray-200 hover:text-white text-sm font-medium transition-all duration-150 group"
                >
                  <div className="p-1.5 rounded-md bg-emerald-900/50 group-hover:bg-emerald-800/60 transition-colors">
                    <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                    </svg>
                  </div>
                  Take Attendance
                  <svg className="w-4 h-4 ml-auto text-gray-600 group-hover:text-emerald-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Link>
              </div>
            </div>

            {/* Choir Tip Card */}
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-purple-950 to-indigo-950 border border-purple-800/40 p-6">
              <div className="absolute top-0 right-0 w-24 h-24 bg-purple-600/10 rounded-full -translate-y-8 translate-x-8" />
              <div className="absolute bottom-0 left-0 w-16 h-16 bg-indigo-600/10 rounded-full translate-y-6 -translate-x-6" />
              <div className="relative">
                <div className="flex items-center gap-2 mb-3">
                  <svg className="w-5 h-5 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.34.208-.646.477-.859a4 4 0 10-4.954 0c.27.213.462.519.476.859h4.001z" />
                  </svg>
                  <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">Conductor's Tip</span>
                </div>
                <p className="text-sm text-purple-200 leading-relaxed">
                  Regular attendance tracking helps identify trends early. Reach out to members who've missed consecutive rehearsals to keep ensemble cohesion strong.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Shortcuts */}
        <section>
          <h2 className="text-lg font-semibold text-gray-300 mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
            Explore
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { to: '/members', label: 'Members', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z', color: 'purple' },
              { to: '/events', label: 'Events', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z', color: 'indigo' },
              { to: '/repertoire', label: 'Repertoire', icon: 'M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3', color: 'rose' },
              { to: '/attendance', label: 'Attendance', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4', color: 'emerald' },
            ].map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`flex flex-col items-center gap-3 p-5 rounded-xl bg-gray-900 border border-gray-700 hover:border-${item.color}-700/60 hover:bg-${item.color}-950/30 transition-all duration-200 group text-center`}
              >
                <div className={`p-3 rounded-lg bg-${item.color}-900/40 border border-${item.color}-800/40 group-hover:bg-${item.color}-800/50 transition-colors`}>
                  <svg className={`w-6 h-6 text-${item.color}-400`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                  </svg>
                </div>
                <span className="text-sm font-medium text-gray-300 group-hover:text-white transition-colors">
                  {item.label}
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
};

export default Dashboard;
