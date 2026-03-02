import type { Config } from "tailwindcss"
import sharedConfig from "@gamole/config/tailwind"

const config: Config = {
  presets: [sharedConfig],
  content: ["./src/**/*.{ts,tsx}"],
}

export default config
