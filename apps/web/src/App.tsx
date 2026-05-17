import { QueryClientProvider } from "@tanstack/react-query";

import { ResearchConsolePage } from "./pages/ResearchConsolePage";
import { queryClient } from "./lib/query-client";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ResearchConsolePage />
    </QueryClientProvider>
  );
}
