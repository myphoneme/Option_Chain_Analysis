/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  basePath: "/optionchain",
  env: {
    NEXT_PUBLIC_API_BASE:
      process.env.NEXT_PUBLIC_API_BASE ||
      "https://quantapi.phoneme.in/optionchain",
  },
};
module.exports = nextConfig;