import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 10 * 60_000,
      refetchOnWindowFocus: false,
      retry: (attempt, error) => {
        if (error instanceof ApiError && !error.retryable) return false;
        return attempt < 1;
      },
    },
    mutations: { retry: false },
  },
});
