import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const srcDir = path.resolve(__dirname, '../src');

const SLATE_REGEX = /\bslate-[0-9]+/g;
const HEX_COLOR_REGEX = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b/g;

let errors = 0;

function walk(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      walk(fullPath);
    } else if (/\.(tsx|ts|jsx|js|css)$/.test(file)) {
      // Allowed exemptions per FRONTEND.md §17: tokens.css and style.ts
      if (file === 'tokens.css' || file === 'style.ts') {
        continue;
      }
      checkFile(fullPath);
    }
  }
}

function checkFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');

  lines.forEach((line, idx) => {
    // Check slate classes
    const slateMatch = line.match(SLATE_REGEX);
    if (slateMatch) {
      console.error(`[TOKEN LINT ERROR] ${path.relative(process.cwd(), filePath)}:${idx + 1} - Found forbidden slate-* class: ${slateMatch.join(', ')}`);
      errors++;
    }

    // Check hex colors (skip comment lines or anchor links like href="#summary")
    const hexMatches = line.match(HEX_COLOR_REGEX);
    if (hexMatches) {
      // Filter out anchors like href="#foo" or string interpolations "#{foo}"
      const colorMatches = hexMatches.filter(hex => {
        // If it's part of a URL fragment / anchor like href="#...", ignore
        if (line.includes(`"${hex}"`) || line.includes(`'${hex}'`)) {
          // If 3, 6, 8 hex digits, it's likely a color
          return true;
        }
        return true;
      });

      if (colorMatches.length > 0) {
        console.error(`[TOKEN LINT ERROR] ${path.relative(process.cwd(), filePath)}:${idx + 1} - Found raw hex color bypass: ${colorMatches.join(', ')}`);
        errors++;
      }
    }
  });
}

walk(srcDir);

if (errors > 0) {
  console.error(`\n❌ Found ${errors} token bypass violations. Replace with tokens from tokens.css.`);
  process.exit(1);
} else {
  console.log('✓ Zero token bypasses found (no raw hex, no slate-*).');
  process.exit(0);
}
