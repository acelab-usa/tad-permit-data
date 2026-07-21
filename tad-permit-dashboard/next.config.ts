import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // sql.js locates its .wasm file relative to its own package directory at
  // runtime (see src/lib/db.ts) -- keep it resolved via plain Node require()
  // rather than bundled/rewritten, so that path resolution stays correct.
  serverExternalPackages: ["sql.js"],
};

export default nextConfig;
