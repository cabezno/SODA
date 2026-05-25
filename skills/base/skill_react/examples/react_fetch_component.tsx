// React component with API fetch + loading/error states — production pattern
import { useState, useEffect, useCallback } from 'react';

interface Item { id: string; name: string; }

interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function useItems() {
  const [state, setState] = useState<FetchState<Item[]>>({ data: null, loading: true, error: null });

  const fetchItems = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }));
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/items`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token') || ''}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setState({ data: json.data ?? json, loading: false, error: null });
    } catch (err) {
      setState({ data: null, loading: false, error: (err as Error).message });
    }
  }, []);

  useEffect(() => { fetchItems(); }, [fetchItems]);
  return { ...state, refetch: fetchItems };
}

export default function ItemList() {
  const { data, loading, error, refetch } = useItems();

  if (loading) return <div className="loading">Loading...</div>;
  if (error)   return <div className="error">Error: {error} <button onClick={refetch}>Retry</button></div>;

  return (
    <ul>
      {(data ?? []).map(item => <li key={item.id}>{item.name}</li>)}
    </ul>
  );
}
