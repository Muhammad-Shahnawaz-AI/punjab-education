/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  basePath: process.env.GITHUB_PAGES === 'true' ? '/punjab-education' : '',
  assetPrefix: process.env.GITHUB_PAGES === 'true' ? '/punjab-education/' : '',
};

export default nextConfig;
