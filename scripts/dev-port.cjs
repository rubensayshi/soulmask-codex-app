const crypto = require("crypto");
const path = require("path");

const MAIN_REPO = "/Users/ruben/work/private/soulmask-codex-app";
const root = path.resolve(__dirname, "..");

function getDevPort() {
  if (root === MAIN_REPO) return 1420;
  const hash = crypto.createHash("md5").update(root).digest();
  const offset = (hash.readUInt16BE(0) % 900) + 100;
  return 1000 + offset;
}

module.exports = { getDevPort, isWorktree: root !== MAIN_REPO };

if (require.main === module) {
  process.stdout.write(String(getDevPort()));
}
