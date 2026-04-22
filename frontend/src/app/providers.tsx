import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

type AppProvidersProps = {
  children: ReactNode;
  queryClient: QueryClient;
};

export function AppProviders({ children, queryClient }: AppProvidersProps) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
