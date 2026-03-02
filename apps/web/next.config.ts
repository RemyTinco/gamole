import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["@gamole/types", "@gamole/config"],
}

export default nextConfig
