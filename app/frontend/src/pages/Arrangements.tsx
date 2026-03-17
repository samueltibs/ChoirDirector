import React, { useState, useEffect, useCallback } from 'react';

interface ArrangementRequest {
  id: string;
  piece_title: string;
  source_type: string;
  target_voicing: string;
  style: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  result_url?: string;
  error_message?: string;
}

const SOURCE_TYPES = [
  'Piano Score',
  'Orchestra Score',
  'Lead Sheet',
  'Guitar Tab',
  'MIDI File',
  'Audio Recording',
  'String Quartet',
  'Band Arrangement',
  'Solo Vocal',
  'Other',
];

const TARGET_VOICINGS = [
  'SATB',
  'SSA',
  'SSAA',
  'SAB',
  'TTBB',
  'SATB + Piano',
  'SSA + Piano',
  'TTBB + Piano',
  'Eight-Part',
  'Unison',
  'Two-Part',
  'Three-Part Mixed',
];

const STYLES = [
  'Classical',
  'Romantic',
  'Contemporary',
  'Gospel',
  'Jazz',
  'A Cappella',
  'Sacred Traditional',
  'Folk',
  'Pop / Commercial',
  'Barbershop',
  'World Music',
];

const statusConfig: Record<ArrangementRequest['status'], { label: string; classes: string }> = {
  pending: {
    label: 'Pending',
    classes: 'bg-yellow-900/40 text-yellow-300 border border-yellow-700/50',
  },
  processing: {
    label: 'Processing',
    classes: 'bg-blue-900/40 text-blue-300 border border-blue-700/50',
  },
  completed: {
    label: 'Completed',
    classes: 'bg-emerald-900/40 text-emerald-300 border border-emerald-700/50',
  },
  failed: {
    label: 'Failed',
    classes: 'bg-red-900/40 text-red-300 border border-red-700/50',
  },
};

const formatDate = (iso: string) => {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
};

const Arrangements: React.FC = () => {
  const [form, setForm] = useState({
    piece_title: '',
    source_type: SOURCE_TYPES[0],
    target_voicing: TARGET_VOICINGS[0],
    style: STYLES[0],
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const [history, setHistory] = useState<ArrangementRequest[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setLoadingHistory(true);
    setHistoryError(null);
    try {
      const res = await fetch('/arrangements');
      if (!res.ok) throw new Error(`Server responded with ${res.status}`);
      const data: ArrangementRequest[] = await res.json();
      setHistory(data);
    } catch (err: unknown) {
      setHistoryError(err instanceof Error ? err.message : 'Failed to load arrangements');
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
    const interval = setInterval(fetchHistory, 15000);
    return () => clearInterval(interval);
  }, [fetchHistory]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setSubmitError(null);
    setSubmitSuccess(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.piece_title.trim()) {
      setSubmitError('Please enter a piece title.');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(false);
    try {
      const res = await fetch('/arrangements', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail || `Server error ${res.status}`);
      }
      setSubmitSuccess(true);
      setForm({
        piece_title: '',
        source_type: SOURCE_TYPES[0],
        target_voicing: TARGET_VOICINGS[0],
        style: STYLES[0],
      });
      await fetchHistory();
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans">
      {/* Header */}
      <header className="bg-gradient-to-r from-gray-900 via-indigo-950 to-gray-900 border-b border-indigo-900/40 shadow-lg">
        <div className="max-w-6xl mx-auto px-6 py-8 flex items-center gap-4">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-indigo-800/50 border border-indigo-600/50 shadow-inner">
            <svg className="w-6 h-6 text-indigo-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z" />
            </svg>
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-wide text-white">AI Choir Arrangements</h1>
            <p className="text-indigo-300 text-sm mt-0.5">Transform any score into a professional choral arrangement</p>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-12">
        {/* Request Form */}
        <section>
          <div className="flex items-center gap-3 mb-6">
            <span className="flex-shrink-0 w-1 h-6 bg-indigo-500 rounded-full" />
            <h2 className="text-xl font-semibold text-white">New Arrangement Request</h2>
          </div>

          <div className="bg-gray-900/80 border border-gray-700/60 rounded-2xl shadow-xl p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Piece Title */}
              <div>
                <label htmlFor="piece_title" className="block text-sm font-medium text-gray-300 mb-1.5">
                  Piece Title <span className="text-indigo-400">*</span>
                </label>
                <input
                  id="piece_title"
                  name="piece_title"
                  type="text"
                  value={form.piece_title}
                  onChange={handleChange}
                  placeholder="e.g. Ave Maria, Hallelujah, Bohemian Rhapsodyâ¦"
                  className="w-full bg-gray-800/70 border border-gray-600/70 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/70 focus:border-indigo-500/50 transition-all duration-200"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Source Type */}
                <div>
                  <label htmlFor="source_type" className="block text-sm font-medium text-gray-300 mb-1.5">
                    Source Type
                  </label>
                  <div className="relative">
                    <select
                      id="source_type"
                      name="source_type"
                      value={form.source_type}
                      onChange={handleChange}
                      className="w-full appearance-none bg-gray-800/70 border border-gray-600/70 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/70 focus:border-indigo-500/50 transition-all duration-200 cursor-pointer pr-10"
                    >
                      {SOURCE_TYPES.map((s) => (
                        <option key={s} value={s} className="bg-gray-800">{s}</option>
                      ))}
                    </select>
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                    </span>
                  </div>
                </div>

                {/* Target Voicing */}
                <div>
                  <label htmlFor="target_voicing" className="block text-sm font-medium text-gray-300 mb-1.5">
                    Target Voicing
                  </label>
                  <div className="relative">
                    <select
                      id="target_voicing"
                      name="target_voicing"
                      value={form.target_voicing}
                      onChange={handleChange}
                      className="w-full appearance-none bg-gray-800/70 border border-gray-600/70 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/70 focus:border-indigo-500/50 transition-all duration-200 cursor-pointer pr-10"
                    >
                      {TARGET_VOICINGS.map((v) => (
                        <option key={v} value={v} className="bg-gray-800">{v}</option>
                      ))}
                    </select>
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                    </span>
                  </div>
                </div>

                {/* Style */}
                <div>
                  <label htmlFor="style" className="block text-sm font-medium text-gray-300 mb-1.5">
                    Style
                  </label>
                  <div className="relative">
                    <select
                      id="style"
                      name="style"
                      value={form.style}
                      onChange={handleChange}
                      className="w-full appearance-none bg-gray-800/70 border border-gray-600/70 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/70 focus:border-indigo-500/50 transition-all duration-200 cursor-pointer pr-10"
                    >
                      {STYLES.map((st) => (
                        <option key={st} value={st} className="bg-gray-800">{st}</option>
                      ))}
                    </select>
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                    </span>
                  </div>
                </div>
              </div>

              {/* Feedback */}
              {submitError && (
                <div className="flex items-start gap-3 bg-red-900/30 border border-red-700/50 text-red-300 rounded-xl px-4 py-3 text-sm">
                  <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  <span>{submitError}</span>
                </div>
              )}
              {submitSuccess && (
                <div className="flex items-start gap-3 bg-emerald-900/30 border border-emerald-700/50 text-emerald-300 rounded-xl px-4 py-3 text-sm">
                  <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  <span>Arrangement request submitted successfully! The AI is now processing your score.</span>
                </div>
              )}

              {/* Submit */}
              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center gap-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 disabled:cursor-not-allowed text-white font-semibold px-8 py-3 rounded-xl shadow-lg shadow-indigo-900/40 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 focus:ring-offset-gray-900"
                >
                  {submitting ? (
                    <>
                      <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                      </svg>
                      Submittingâ¦
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                      Request Arrangement
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </section>

        {/* History Table */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <span className="flex-shrink-0 w-1 h-6 bg-indigo-500 rounded-full" />
              <h2 className="text-xl font-semibold text-white">Arrangement History</h2>
            </div>
            <button
              onClick={fetchHistory}
              disabled={loadingHistory}
              className="inline-flex items-center gap-2 text-sm text-indigo-300 hover:text-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 focus:outline-none"
            >
              <svg className={`w-4 h-4 ${loadingHistory ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
              Refresh
            </button>
          </div>

          <div className="bg-gray-900/80 border border-gray-700/60 rounded-2xl shadow-xl overflow-hidden">
            {historyError && (
              <div className="flex items-center gap-3 bg-red-900/30 border-b border-red-800/40 text-red-300 px-6 py-4 text-sm">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                {historyError}
              </div>
            )}

            {loadingHistory && history.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 gap-4">
                <svg className="w-10 h-10 text-indigo-400 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                <p className="text-gray-500 text-sm">Loading arrangementsâ¦</p>
              </div>
            ) : history.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 gap-4">
                <div className="w-16 h-16 rounded-full bg-gray-800/80 border border-gray-700/50 flex items-center justify-center">
                  <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z" />
                  </svg>
                </div>
                <div className="text-center">
                  <p className="text-gray-400 font-medium">No arrangements yet</p>
                  <p className="text-gray-600 text-sm mt-1">Submit your first request above to get started</p>
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700/60 bg-gray-800/50">
                      <th className="text-left px-6 py-4 font-semibold text-gray-400 uppercase tracking-wider text-xs">Piece Title</th>
                      <th className="text-left px-6 py-4 font-semibold text-gray-400 uppercase tracking-wider text-xs">Source</th>
                      <th className="text-left px-6 py-4 font-semibold text-gray-400 uppercase tracking-wider text-xs">Voicing</th>
                      <th className="text-left px-6 py-4 font-semibold text-gray-400 uppercase tracking-wider text-xs">Style</th>
                      <th className="text-left px-6 py-4 font-semibold text-gray-400 uppercase tracking-wider text-xs">Status</th>
                      <th className="text-left px-6 py-4 font-semibold text-gray-400 uppercase tracking-wider text-xs">Submitted</th>
                      <th className="text-left px-6 py-4 font-semibold text-gray-400 uppercase tracking-wider text-xs">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60">
                    {history.map((item) => {
                      const badge = statusConfig[item.status] ?? statusConfig.pending;
                      return (
                        <tr
                          key={item.id}
                          className="hover:bg-gray-800/30 transition-colors duration-150 group"
                        >
                          <td className="px-6 py-4">
                            <span className="font-medium text-white group-hover:text-indigo-200 transition-colors">
                              {item.piece_title}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-gray-400">{item.source_type}</td>
                          <td className="px-6 py-4">
                            <span className="inline-block bg-indigo-900/40 text-indigo-300 border border-indigo-800/50 text-xs font-medium px-2.5 py-1 rounded-lg">
                              {item.target_voicing}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-gray-400">{item.style}</td>
                          <td className="px-6 py-4">
                            <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-lg ${badge.classes}`}>
                              {item.status === 'processing' && (
                                <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                                </svg>
                              )}
                              {item.status === 'completed' && (
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
                              )}
                              {item.status === 'failed' && (
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" /></svg>
                              )}
                              {item.status === 'pending' && (
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                              )}
                              {badge.label}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-gray-500 whitespace-nowrap">
                            {formatDate(item.created_at)}
                          </td>
                          <td className="px-6 py-4">
                            {item.status === 'completed' && item.result_url ? (
                              <a
                                href={item.result_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-300 hover:text-emerald-100 transition-colors"
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                                Download
                              </a>
                            ) : item.status === 'failed' && item.error_message ? (
                              <span
                                title={item.error_message}
                                className="inline-flex items-center gap-1 text-xs text-red-400 cursor-help"
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                View Error
                              </span>
                            ) : (
                              <span className="text-gray-700 text-xs">â</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {history.length > 0 && (
            <p className="text-center text-gray-600 text-xs mt-4">
              Showing {history.length} arrangement{history.length !== 1 ? 's' : ''} Â· Auto-refreshes every 15 seconds
            </p>
          )}
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800/60 mt-16">
        <div className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
          <p className="text-gray-600 text-sm">AI Choir Arrangements</p>
          <p className="text-gray-700 text-xs">Powered by generative music AI</p>
        </div>
      </footer>
    </div>
  );
};

export default Arrangements;
