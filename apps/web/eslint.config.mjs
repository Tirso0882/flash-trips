import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const bffOnlyPatterns = [
  {
    group: ["@flash-trips/api-client", "@flash-trips/api-client/*"],
    message: "UI routes must cross the Next.js BFF interface.",
  },
  {
    regex: "(^|/)lib/server/",
    message: "UI routes must cross the Next.js BFF interface.",
  },
];

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  {
    files: ["app/**/*.tsx"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: bffOnlyPatterns,
        },
      ],
    },
  },
  {
    files: ["app/(planner)/**/*.ts", "app/(planner)/**/*.tsx"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            ...bffOnlyPatterns,
            {
              group: [
                "app/(operator)/*",
                "app/(operator)/**",
                "**/(operator)/*",
                "**/(operator)/**",
              ],
              message: "Planner and Operator surfaces must remain separate.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["app/(operator)/**/*.ts", "app/(operator)/**/*.tsx"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            ...bffOnlyPatterns,
            {
              group: [
                "app/(planner)/*",
                "app/(planner)/**",
                "**/(planner)/*",
                "**/(planner)/**",
              ],
              message: "Planner and Operator surfaces must remain separate.",
            },
          ],
        },
      ],
    },
  },
  globalIgnores([".next/**", "next-env.d.ts"]),
]);
