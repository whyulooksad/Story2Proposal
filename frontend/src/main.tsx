import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient } from "@tanstack/react-query";

import { AppProviders } from "./app/providers";
import { AppRouter } from "./app/router";
import "./styles/global.css";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProviders queryClient={queryClient}>
      <AppRouter />
    </AppProviders>
  </React.StrictMode>,
);
