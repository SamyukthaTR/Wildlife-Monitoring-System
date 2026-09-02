/** @type {import('next').NextConfig} */
const nextConfig = {
  // Smaller, self-contained production image (this project's frontend
  // Dockerfile "prod" stage copies only .next/standalone + .next/static + public).
  output: 'standalone',
};

export default nextConfig;
