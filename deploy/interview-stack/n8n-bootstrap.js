const { spawn } = require("node:child_process");

function runN8n(args) {
  return new Promise((resolve, reject) => {
    const child = spawn("n8n", args, { stdio: "inherit" });
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`n8n ${args.join(" ")} exited with ${signal || code}`));
    });
  });
}

async function main() {
  await runN8n(["import:workflow", "--input=/workflows/n8n-grader-workflow.json"]);
  await runN8n(["publish:workflow", "--id=interview-grader-workflow"]);

  const server = spawn("n8n", ["start"], { stdio: "inherit" });
  server.once("error", (error) => {
    console.error(error);
    process.exitCode = 1;
  });
  server.once("exit", (code, signal) => {
    process.exitCode = signal ? 1 : code ?? 1;
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
