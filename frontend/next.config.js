/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Disable SSR for this protected app - all pages use client-side rendering
  // This prevents hydration mismatches and SSR-related issues
  experimental: {
    // Optimize for client-side app
  },
  // Force dynamic rendering for all routes (no static generation)
  // This is appropriate for authenticated apps where content is user-specific
  output: undefined, // Keep as server-rendered but with dynamic routes
};

module.exports = nextConfig;
