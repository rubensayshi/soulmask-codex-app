const { getDevPort, isWorktree } = require("./dev-port.cjs");

if (!isWorktree) {
  process.stdout.write("{}");
} else {
  const port = getDevPort();
  process.stdout.write(
    JSON.stringify({ build: { devUrl: `http://localhost:${port}` } })
  );
}
