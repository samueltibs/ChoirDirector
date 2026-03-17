import React, { useState, useEffect, useCallback } from 'react';

interface Piece {
  id: number;
  title: string;
  composer: string;
  genre: string;
  voicing: string;
  difficulty: number;
  description?: string;
  duration?: string;
  language?: string;
  publisher?: string;
  notes?: string;
  created_at?: string;
}

const API_BASE = '/api';

const StarRating: React.FC<{ rating: number; interactive?: boolean; onChange?: (val: number) => void }> = ({
  rating,
  interactive = false,
  onChange,
}) => {
  const [hovered, setHovered] = useState(0);
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={!interactive}
          className={`text-lg transition-colors ${
            interactive ? 'cursor-pointer' : 'cursor-default'
          } ${
            star <= (interactive ? hovered || rating : rating)
              ? 'text-amber-400'
              : 'text-slate-600'
          }`}
          onMouseEnter={() => interactive && setHovered(star)}
          onMouseLeave={() => interactive && setHovered(0)}
          onClick={() => interactive && onChange && onChange(star)}
        >
          â
        </button>
      ))}
    </div>
  );
};

const GENRES = ['Sacred', 'Secular', 'Gospel', 'Classical', 'Contemporary', 'Folk', 'Jazz', 'World', 'Other'];
const VOICINGS = ['SATB', 'SSA', 'TTBB', 'SAB', 'SA', 'TB', 'Unison', 'SSAA', 'TTBB', 'Other'];

const defaultForm = {
  title: '',
  composer: '',
  genre: 'Sacred',
  voicing: 'SATB',
  difficulty: 3,
  description: '',
  duration: '',
  language: '',
  publisher: '',
  notes: '',
};

const Repertoire: React.FC = () => {
  const [pieces, setPieces] = useState<Piece[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filterGenre, setFilterGenre] = useState('');
  const [filterVoicing, setFilterVoicing] = useState('');
  const [filterDifficulty, setFilterDifficulty] = useState(0);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedPiece, setSelectedPiece] = useState<Piece | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [formData, setFormData] = useState(defaultForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const fetchPieces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/repertoire`);
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setPieces(Array.isArray(data) ? data : data.items ?? []);
    } catch (e: any) {
      setError(e.message || 'Failed to load repertoire');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPieces();
  }, [fetchPieces]);

  const fetchDetail = async (id: number) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/repertoire/${id}`);
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setSelectedPiece(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load piece details');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim()) { setFormError('Title is required'); return; }
    if (!formData.composer.trim()) { setFormError('Composer is required'); return; }
    setSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch(`${API_BASE}/repertoire`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${res.status}`);
      }
      setShowAddModal(false);
      setFormData(defaultForm);
      await fetchPieces();
    } catch (e: any) {
      setFormError(e.message || 'Failed to add piece');
    } finally {
      setSubmitting(false);
    }
  };

  const filteredPieces = pieces.filter((p) => {
    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      p.title.toLowerCase().includes(q) ||
      p.composer.toLowerCase().includes(q) ||
      (p.genre || '').toLowerCase().includes(q) ||
      (p.voicing || '').toLowerCase().includes(q);
    const matchGenre = !filterGenre || p.genre === filterGenre;
    const matchVoicing = !filterVoicing || p.voicing === filterVoicing;
    const matchDiff = !filterDifficulty || p.difficulty === filterDifficulty;
    return matchSearch && matchGenre && matchVoicing && matchDiff;
  });

  const genreColors: Record<string, string> = {
    Sacred: 'bg-indigo-900 text-indigo-200',
    Secular: 'bg-teal-900 text-teal-200',
    Gospel: 'bg-purple-900 text-purple-200',
    Classical: 'bg-blue-900 text-blue-200',
    Contemporary: 'bg-cyan-900 text-cyan-200',
    Folk: 'bg-green-900 text-green-200',
    Jazz: 'bg-yellow-900 text-yellow-200',
    World: 'bg-rose-900 text-rose-200',
    Other: 'bg-slate-700 text-slate-200',
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 text-slate-100 font-sans">
      {/* Header */}
      <div className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">ð¼</span>
            <div>
              <h1 className="text-2xl font-bold tracking-wide text-white">Repertoire Library</h1>
              <p className="text-xs text-slate-400">{pieces.length} piece{pieces.length !== 1 ? 's' : ''} in library</p>
            </div>
          </div>
          <button
            onClick={() => { setShowAddModal(true); setFormData(defaultForm); setFormError(null); }}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-lg shadow-indigo-900/40"
          >
            <span className="text-lg leading-none">+</span> Add Piece
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search & Filters */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 mb-8 flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-lg">ð</span>
            <input
              type="text"
              placeholder="Search title, composer, genre, voicing..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>
          <select
            value={filterGenre}
            onChange={(e) => setFilterGenre(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Genres</option>
            {GENRES.map((g) => <option key={g}>{g}</option>)}
          </select>
          <select
            value={filterVoicing}
            onChange={(e) => setFilterVoicing(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Voicings</option>
            {VOICINGS.map((v) => <option key={v}>{v}</option>)}
          </select>
          <select
            value={filterDifficulty}
            onChange={(e) => setFilterDifficulty(Number(e.target.value))}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value={0}>All Difficulties</option>
            {[1, 2, 3, 4, 5].map((d) => (
              <option key={d} value={d}>{'â'.repeat(d)} {'â'.repeat(5 - d)}</option>
            ))}
          </select>
          {(search || filterGenre || filterVoicing || filterDifficulty > 0) && (
            <button
              onClick={() => { setSearch(''); setFilterGenre(''); setFilterVoicing(''); setFilterDifficulty(0); }}
              className="text-sm text-slate-400 hover:text-white transition-colors px-2 whitespace-nowrap"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 mb-6 flex items-center gap-3">
            <span className="text-xl">â ï¸</span>
            <span>{error}</span>
            <button onClick={fetchPieces} className="ml-auto text-sm underline hover:no-underline">Retry</button>
          </div>
        )}

        {/* Loading */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-32 gap-4">
            <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-slate-400">Loading repertoire...</p>
          </div>
        ) : filteredPieces.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 gap-4 text-center">
            <span className="text-6xl opacity-40">ðµ</span>
            <p className="text-slate-400 text-lg">
              {pieces.length === 0 ? 'Your library is empty. Add your first piece!' : 'No pieces match your search.'}
            </p>
            {pieces.length === 0 && (
              <button
                onClick={() => setShowAddModal(true)}
                className="mt-2 bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2.5 rounded-lg font-semibold transition-colors"
              >
                Add First Piece
              </button>
            )}
          </div>
        ) : (
          <>
            <p className="text-xs text-slate-500 mb-4">{filteredPieces.length} result{filteredPieces.length !== 1 ? 's' : ''}</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
              {filteredPieces.map((piece) => (
                <div
                  key={piece.id}
                  onClick={() => fetchDetail(piece.id)}
                  className="group bg-slate-900 border border-slate-800 hover:border-indigo-700 rounded-xl p-5 cursor-pointer transition-all duration-200 hover:shadow-xl hover:shadow-indigo-950/60 hover:-translate-y-0.5"
                >
                  <div className="flex items-start justify-between mb-3">
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                        genreColors[piece.genre] || 'bg-slate-700 text-slate-200'
                      }`}
                    >
                      {piece.genre || 'Unknown'}
                    </span>
                    <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full">{piece.voicing}</span>
                  </div>
                  <h3 className="font-bold text-white text-base leading-snug mb-1 group-hover:text-indigo-300 transition-colors line-clamp-2">
                    {piece.title}
                  </h3>
                  <p className="text-slate-400 text-sm mb-4 truncate">{piece.composer}</p>
                  <div className="flex items-center justify-between">
                    <StarRating rating={piece.difficulty} />
                    {piece.duration && (
                      <span className="text-xs text-slate-500">â± {piece.duration}</span>
                    )}
                  </div>
                  {piece.language && (
                    <p className="text-xs text-slate-600 mt-2 truncate">ð {piece.language}</p>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Detail Modal */}
      {(selectedPiece || detailLoading) && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          onClick={() => !detailLoading && setSelectedPiece(null)}
        >
          <div
            className="relative bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {detailLoading ? (
              <div className="flex items-center justify-center py-24">
                <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : selectedPiece ? (
              <>
                <div className="sticky top-0 bg-slate-900 border-b border-slate-800 px-6 py-4 flex items-start justify-between rounded-t-2xl z-10">
                  <div className="pr-4">
                    <h2 className="text-xl font-bold text-white leading-tight">{selectedPiece.title}</h2>
                    <p className="text-indigo-400 text-sm mt-0.5">{selectedPiece.composer}</p>
                  </div>
                  <button
                    onClick={() => setSelectedPiece(null)}
                    className="text-slate-400 hover:text-white text-2xl leading-none p-1 transition-colors flex-shrink-0"
                  >
                    â
                  </button>
                </div>
                <div className="px-6 py-5 space-y-5">
                  <div className="flex flex-wrap gap-2">
                    <span className={`text-xs font-semibold px-3 py-1 rounded-full ${ genreColors[selectedPiece.genre] || 'bg-slate-700 text-slate-200' }`}>
                      {selectedPiece.genre}
                    </span>
                    <span className="text-xs bg-slate-800 text-slate-300 px-3 py-1 rounded-full">{selectedPiece.voicing}</span>
                    {selectedPiece.language && (
                      <span className="text-xs bg-slate-800 text-slate-300 px-3 py-1 rounded-full">ð {selectedPiece.language}</span>
                    )}
                    {selectedPiece.duration && (
                      <span className="text-xs bg-slate-800 text-slate-300 px-3 py-1 rounded-full">â± {selectedPiece.duration}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-400">Difficulty:</span>
                    <StarRating rating={selectedPiece.difficulty} />
                    <span className="text-xs text-slate-500">({selectedPiece.difficulty}/5)</span>
                  </div>
                  {selectedPiece.description && (
                    <div>
                      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">Description</h4>
                      <p className="text-slate-300 text-sm leading-relaxed">{selectedPiece.description}</p>
                    </div>
                  )}
                  {selectedPiece.publisher && (
                    <div>
                      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-1">Publisher</h4>
                      <p className="text-slate-300 text-sm">{selectedPiece.publisher}</p>
                    </div>
                  )}
                  {selectedPiece.notes && (
                    <div>
                      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">Notes</h4>
                      <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-4">
                        <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">{selectedPiece.notes}</p>
                      </div>
                    </div>
                  )}
                  {selectedPiece.created_at && (
                    <p className="text-xs text-slate-600">Added: {new Date(selectedPiece.created_at).toLocaleDateString()}</p>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}

      {/* Add Piece Modal */}
      {showAddModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          onClick={() => setShowAddModal(false)}
        >
          <div
            className="relative bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-xl max-h-[95vh] overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-slate-900 border-b border-slate-800 px-6 py-4 flex items-center justify-between rounded-t-2xl z-10">
              <h2 className="text-lg font-bold text-white">Add New Piece</h2>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-white text-2xl leading-none p-1 transition-colors"
              >
                â
              </button>
            </div>
            <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
              {formError && (
                <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
                  {formError}
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">
                    Title <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="e.g. Lux Aeterna"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">
                    Composer <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.composer}
                    onChange={(e) => setFormData({ ...formData, composer: e.target.value })}
                    placeholder="e.g. Morten Lauridsen"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Genre</label>
                  <select
                    value={formData.genre}
                    onChange={(e) => setFormData({ ...formData, genre: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    {GENRES.map((g) => <option key={g}>{g}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Voicing</label>
                  <select
                    value={formData.voicing}
                    onChange={(e) => setFormData({ ...formData, voicing: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    {VOICINGS.map((v) => <option key={v}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Duration</label>
                  <input
                    type="text"
                    value={formData.duration}
                    onChange={(e) => setFormData({ ...formData, duration: e.target.value })}
                    placeholder="e.g. 5:30"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Language</label>
                  <input
                    type="text"
                    value={formData.language}
                    onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                    placeholder="e.g. Latin"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Difficulty</label>
                  <div className="flex items-center gap-3">
                    <StarRating
                      rating={formData.difficulty}
                      interactive
                      onChange={(val) => setFormData({ ...formData, difficulty: val })}
                    />
                    <span className="text-sm text-slate-400">{formData.difficulty}/5</span>
                  </div>
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Publisher</label>
                  <input
                    type="text"
                    value={formData.publisher}
                    onChange={(e) => setFormData({ ...formData, publisher: e.target.value })}
                    placeholder="e.g. Hal Leonard"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Description</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={3}
                    placeholder="Brief description of the piece..."
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Director Notes</label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={3}
                    placeholder="Performance notes, rehearsal tips..."
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2.5 rounded-lg font-semibold text-sm transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 disabled:cursor-not-allowed text-white px-4 py-2.5 rounded-lg font-semibold text-sm transition-colors flex items-center justify-center gap-2"
                >
                  {submitting ? (
                    <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Saving...</>
                  ) : (
                    'Add to Library'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Repertoire;
