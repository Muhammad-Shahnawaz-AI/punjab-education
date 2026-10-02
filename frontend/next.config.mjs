/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  basePath: process.env.NODE_ENV === 'production' ? '/punjab-education' : '',
  assetPrefix: process.env.NODE_ENV === 'production' ? '/punjab-education/' : '',
};

export default nextConfig;
