import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const srcDir = path.resolve(__dirname, '../src');

// Accusatory terms forbidden by FRONTEND.md §2.6 and PRD P7-G6
const FORBIDDEN_ACCUSATORY_TERMS = [
  /\bguilty\b/i,
  /\bcriminal\b/i,
  /\bfraudster\b/i,
  /\bculprit\b/i,
  /\bscammer\b/i,
  /\bfraudulent actor\b/i,
  /\bcrook\b/i,
  /\bperpetrator\b/i,
];

let errors = 0;

function walk(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      walk(fullPath);
    } else if (/\.(tsx|ts|jsx|js)$/.test(file)) {
      checkFile(fullPath);
    }
  }
}

function checkFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');

  lines.forEach((line, idx) => {
    for (const pattern of FORBIDDEN_ACCUSATORY_TERMS) {
      if (pattern.test(line)) {
        console.error(`[COPY LINT ERROR] ${path.relative(process.cwd(), filePath)}:${idx + 1} - Found accusatory terminology matching ${pattern}: "${line.trim()}"`);
        errors++;
      }
    }
  });
}

walk(srcDir);

if (errors > 0) {
  console.error(`\n❌ Found ${errors} accusatory copy violations. Replace with neutral phrasing (e.g., 'linked', 'finding', 'lead').`);
  process.exit(1);
} else {
  console.log('✓ Zero accusatory terms found across copy and UI templates.');
  process.exit(0);
}
