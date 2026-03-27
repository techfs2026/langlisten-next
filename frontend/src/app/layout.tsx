"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import "./globals.css";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000,
            retry: 1,
          },
        },
      })
  );

  return (
    <html lang="zh-CN">
      <body>
        <AntdRegistry>
          <QueryClientProvider client={queryClient}>
            {children}
          </QueryClientProvider>
        </AntdRegistry>
      </body>
    </html>
  );
}