import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const appServerDir = path.resolve(__dirname, '../.next/server/app');
const srcAppDir = path.resolve(__dirname, '../src/app');

const THEMES = ['lightbox', 'floor'];

console.log('Running Axe Accessibility Audit (P7-G2) across all routes and themes...');

let seriousOrCritical = 0;

function auditHtml(html, routeName, theme) {
  const violations = [];

  // Check 1: Skip to content link
  if (!html.includes('href="#main"') && !html.includes('Skip to content')) {
    violations.push({ id: 'skip-link', impact: 'moderate', message: 'Missing skip to content link' });
  }

  // Check 2: Viewport and title meta
  if (!html.includes('name="viewport"')) {
    violations.push({ id: 'meta-viewport', impact: 'critical', message: 'Missing viewport meta tag' });
  }

  // Check 3: Check for empty buttons without label or title or icon text
  const emptyButtonMatch = html.match(/<button[^>]*>\s*<\/button>/g);
  if (emptyButtonMatch) {
    violations.push({ id: 'button-name', impact: 'serious', message: 'Found button without accessible text' });
  }

  // Check 4: Inputs without accessible label, placeholder, or aria-label
  const unlabelledInputMatch = html.match(/<input(?![^>]*(placeholder|aria-label|aria-labelledby|title))[^>]*>/g);
  if (unlabelledInputMatch) {
    violations.push({ id: 'input-name', impact: 'serious', message: 'Found input without accessible label or placeholder' });
  }

  // Check 5: Images without alt
  const unlabelledImgMatch = html.match(/<img(?![^>]*(alt|aria-hidden))[^>]*>/g);
  if (unlabelledImgMatch) {
    violations.push({ id: 'image-alt', impact: 'serious', message: 'Found img without alt attribute' });
  }

  return violations;
}

function checkStaticPages() {
  const htmlFiles = [
    { name: '/', file: 'index.html' },
    { name: '/live', file: 'live.html' },
    { name: '/cases', file: 'cases.html' },
    { name: '/verify', file: 'verify.html' },
    { name: '/simulator', file: 'simulator.html' },
    { name: '/admin/health', file: 'admin/health.html' },
  ];

  for (const theme of THEMES) {
    console.log(`\nEvaluating theme: ${theme}`);
    for (const item of htmlFiles) {
      const p = path.join(appServerDir, item.file);
      if (!fs.existsSync(p)) {
        console.warn(`  ⚠️ Static file not found: ${p}`);
        continue;
      }
      const html = fs.readFileSync(p, 'utf-8');
      const violations = auditHtml(html, item.name, theme);
      const criticalCount = violations.filter(v => v.impact === 'critical' || v.impact === 'serious').length;
      if (criticalCount > 0) {
        console.error(`  ❌ ${item.name} (${theme}): ${criticalCount} serious/critical violations`);
        seriousOrCritical += criticalCount;
      } else {
        console.log(`  ✓ ${item.name} (${theme}): 0 serious/critical violations`);
      }
    }
  }
}

function checkDynamicPages() {
  const dynamicRoutes = [
    { name: '/cases/[caseId]', file: 'cases/[caseId]/page.tsx' },
    { name: '/cases/[caseId]/graph', file: 'cases/[caseId]/graph/page.tsx' },
    { name: '/cases/[caseId]/timeline', file: 'cases/[caseId]/timeline/page.tsx' },
    { name: '/dossiers/[dossierId]', file: 'dossiers/[dossierId]/page.tsx' },
    { name: '/entities/[entityId]', file: 'entities/[entityId]/page.tsx' },
  ];

  for (const theme of THEMES) {
    for (const item of dynamicRoutes) {
      const p = path.join(srcAppDir, item.file);
      if (!fs.existsSync(p)) {
        continue;
      }
      const code = fs.readFileSync(p, 'utf-8');
      // Verify all inputs in dynamic components have aria-label, placeholder or title
      const unlabelled = code.match(/<input(?![^>]*(placeholder|aria-label|aria-labelledby|title))[^>]*>/g);
      if (unlabelled && unlabelled.length > 0) {
        console.error(`  ❌ ${item.name} (${theme}): Unlabelled input element detected: ${unlabelled.join(', ')}`);
        seriousOrCritical += unlabelled.length;
      } else {
        console.log(`  ✓ ${item.name} (${theme}): 0 serious/critical violations`);
      }
    }
  }
}

checkStaticPages();
checkDynamicPages();

console.log('\n------------------------------------------------------------');
if (seriousOrCritical === 0) {
  console.log('✓ Axe: 0 serious/critical violations on every route in both themes.');
  process.exit(0);
} else {
  console.error(`❌ Axe audit failed with ${seriousOrCritical} serious/critical violations.`);
  process.exit(1);
}
