import { execSync } from "node:child_process"

const required = "11.6.4"

function isAtLeast(current, minimum) {
  const normalize = (v) => v.split(".").map((part) => Number.parseInt(part, 10) || 0)
  const currentParts = normalize(current)
  const minimumParts = normalize(minimum)
  const maxLength = Math.max(currentParts.length, minimumParts.length)

  for (let i = 0; i < maxLength; i++) {
    const currentValue = currentParts[i] ?? 0
    const minimumValue = minimumParts[i] ?? 0
    if (currentValue > minimumValue) return true
    if (currentValue < minimumValue) return false
  }
  return true
}

function assertNpmVersion() {
  const npmVersion = execSync("npm --version").toString().trim()
  if (!isAtLeast(npmVersion, required)) {
    console.error(`npm ${required} or newer is required. Found ${npmVersion}.`)
    console.error("Please upgrade with: npm install -g npm@11.6.4")
    process.exit(1)
  }
  console.log(`npm version OK (found ${npmVersion}, requires >= ${required}).`)
}

assertNpmVersion()
