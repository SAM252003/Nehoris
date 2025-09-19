import React, { memo, useMemo, Suspense, lazy } from 'react';

// Composant lazy loading pour les listes importantes
const LazyResultList = lazy(() => import('./ResultList'));

// Composant optimisé avec memo pour éviter les re-renders inutiles
export const OptimizedResultCard = memo<{
  title: string;
  content: string;
  brand?: string;
  matches?: number;
}>(({ title, content, brand, matches }) => {
  // Calcul memoizé des statistiques
  const stats = useMemo(() => {
    if (!content || !matches) return null;

    return {
      wordCount: content.split(' ').length,
      readTime: Math.ceil(content.split(' ').length / 200), // 200 mots/min
      brandMentions: matches
    };
  }, [content, matches]);

  return (
    <div className="p-4 border rounded-lg bg-white shadow-sm hover:shadow-md transition-shadow">
      <h3 className="font-semibold text-lg mb-2">{title}</h3>

      {brand && (
        <div className="inline-block px-2 py-1 bg-blue-100 text-blue-800 text-sm rounded mb-2">
          {brand}
        </div>
      )}

      <p className="text-gray-700 line-clamp-3 mb-2">{content}</p>

      {stats && (
        <div className="flex gap-4 text-sm text-gray-500">
          <span>{stats.wordCount} mots</span>
          <span>{stats.readTime} min de lecture</span>
          {stats.brandMentions > 0 && (
            <span className="text-green-600 font-medium">
              {stats.brandMentions} mentions
            </span>
          )}
        </div>
      )}
    </div>
  );
});

// Composant de pagination virtualisée pour grandes listes
export const VirtualizedList = memo<{
  items: any[];
  itemHeight: number;
  containerHeight: number;
  renderItem: (item: any, index: number) => React.ReactNode;
}>(({ items, itemHeight, containerHeight, renderItem }) => {
  const [scrollTop, setScrollTop] = React.useState(0);

  const visibleItems = useMemo(() => {
    const startIndex = Math.floor(scrollTop / itemHeight);
    const visibleCount = Math.ceil(containerHeight / itemHeight) + 2; // +2 pour le buffer
    const endIndex = Math.min(startIndex + visibleCount, items.length);

    return {
      startIndex,
      endIndex,
      items: items.slice(startIndex, endIndex),
      totalHeight: items.length * itemHeight,
      offsetY: startIndex * itemHeight
    };
  }, [items, itemHeight, containerHeight, scrollTop]);

  return (
    <div
      className="overflow-auto"
      style={{ height: containerHeight }}
      onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
    >
      <div style={{ height: visibleItems.totalHeight, position: 'relative' }}>
        <div
          style={{
            transform: `translateY(${visibleItems.offsetY}px)`,
            position: 'absolute',
            width: '100%'
          }}
        >
          {visibleItems.items.map((item, index) =>
            renderItem(item, visibleItems.startIndex + index)
          )}
        </div>
      </div>
    </div>
  );
});

// Skeleton loaders pour les états de chargement
export const ResultSkeleton = memo(() => (
  <div className="p-4 border rounded-lg bg-white animate-pulse">
    <div className="h-6 bg-gray-200 rounded mb-2 w-3/4"></div>
    <div className="h-4 bg-gray-200 rounded mb-2 w-1/4"></div>
    <div className="space-y-2">
      <div className="h-3 bg-gray-200 rounded w-full"></div>
      <div className="h-3 bg-gray-200 rounded w-5/6"></div>
      <div className="h-3 bg-gray-200 rounded w-4/6"></div>
    </div>
    <div className="flex gap-4 mt-3">
      <div className="h-3 bg-gray-200 rounded w-16"></div>
      <div className="h-3 bg-gray-200 rounded w-20"></div>
      <div className="h-3 bg-gray-200 rounded w-24"></div>
    </div>
  </div>
));

// Composant d'erreur optimisé
export const ErrorBoundary = React.Component<
  { children: React.ReactNode; fallback?: React.ComponentType },
  { hasError: boolean }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      const FallbackComponent = this.props.fallback || DefaultErrorFallback;
      return <FallbackComponent />;
    }

    return this.props.children;
  }
};

const DefaultErrorFallback = () => (
  <div className="p-6 text-center">
    <div className="text-red-500 text-6xl mb-4">⚠️</div>
    <h2 className="text-xl font-semibold text-gray-800 mb-2">
      Oups, quelque chose s'est mal passé
    </h2>
    <p className="text-gray-600 mb-4">
      Une erreur inattendue s'est produite. Veuillez rafraîchir la page.
    </p>
    <button
      onClick={() => window.location.reload()}
      className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
    >
      Rafraîchir la page
    </button>
  </div>
);

// Hook pour optimiser les images avec lazy loading
export const useImageOptimization = () => {
  const [loadedImages, setLoadedImages] = React.useState(new Set<string>());

  const loadImage = React.useCallback((src: string) => {
    return new Promise<void>((resolve, reject) => {
      if (loadedImages.has(src)) {
        resolve();
        return;
      }

      const img = new Image();
      img.onload = () => {
        setLoadedImages(prev => new Set(prev).add(src));
        resolve();
      };
      img.onerror = reject;
      img.src = src;
    });
  }, [loadedImages]);

  return { loadImage, isImageLoaded: (src: string) => loadedImages.has(src) };
};