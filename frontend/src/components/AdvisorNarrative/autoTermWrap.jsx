// Lightweight narrative renderer.
//
// Handles the markdown subset that LLMs commonly emit (paragraphs, ## / ###
// headings, --- horizontal rules, * / - bullet lists, **bold**, *italic*) and
// automatically wraps glossary terms in <Term> tooltips on first occurrence
// per block.

import { glossary } from '../../data/glossary.js';

function buildPatterns() {
  const out = [];
  for (const [id, entry] of Object.entries(glossary)) {
    const phrases = new Set();
    phrases.add(id.replace(/-/g, ' '));
    const cleanTitle = entry.title.replace(/\s*\([^)]*\)\s*/g, '').trim().toLowerCase();
    phrases.add(cleanTitle);
    if (entry.aliases) entry.aliases.forEach((a) => phrases.add(a.toLowerCase()));
    for (const phrase of phrases) {
      if (phrase) out.push({ id, phrase });
    }
  }
  out.sort((a, b) => b.phrase.length - a.phrase.length);
  return out;
}

const PATTERNS = buildPatterns();

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const MASTER_RE = new RegExp(
  `\\b(${PATTERNS.map((p) => escapeRegex(p.phrase)).join('|')})\\b`,
  'i',
);

function findId(matchedPhrase) {
  const lower = matchedPhrase.toLowerCase();
  return PATTERNS.find((p) => p.phrase === lower)?.id;
}

function wrapTerms(text, wrapped, TermComponent, keyPrefix) {
  const nodes = [];
  let remaining = text;
  let key = 0;
  while (remaining) {
    const m = remaining.match(MASTER_RE);
    if (!m) {
      nodes.push(remaining);
      break;
    }
    const start = m.index;
    const phrase = m[0];
    if (start > 0) nodes.push(remaining.slice(0, start));
    const id = findId(phrase);
    if (id && !wrapped.has(id)) {
      wrapped.add(id);
      nodes.push(
        <TermComponent key={`${keyPrefix}-t${key++}`} id={id}>{phrase}</TermComponent>,
      );
    } else {
      nodes.push(phrase);
    }
    remaining = remaining.slice(start + phrase.length);
  }
  return nodes;
}

// Inline pass: split on **bold** and *italic*, recursively wrap glossary terms
// in plain-text runs. ``wrapped`` is mutated so glossary terms only wrap once
// per block.
function renderInline(text, wrapped, TermComponent, keyPrefix) {
  if (!text) return [];

  // **bold** first (so `**a**` beats nested italic parsing).
  const boldRe = /\*\*([^*\n]+?)\*\*/g;
  const segments = [];
  let last = 0;
  for (const m of text.matchAll(boldRe)) {
    if (m.index > last) segments.push({ kind: 'text', value: text.slice(last, m.index) });
    segments.push({ kind: 'bold', value: m[1] });
    last = m.index + m[0].length;
  }
  if (last < text.length) segments.push({ kind: 'text', value: text.slice(last) });

  // *italic* on the plain-text segments only. Negative lookarounds avoid eating
  // half of an already-matched ** sequence.
  const italicRe = /(?<!\*)\*([^*\n]+?)\*(?!\*)/g;
  const expanded = [];
  for (const seg of segments) {
    if (seg.kind !== 'text') { expanded.push(seg); continue; }
    let l = 0;
    for (const m of seg.value.matchAll(italicRe)) {
      if (m.index > l) expanded.push({ kind: 'text', value: seg.value.slice(l, m.index) });
      expanded.push({ kind: 'italic', value: m[1] });
      l = m.index + m[0].length;
    }
    if (l < seg.value.length) expanded.push({ kind: 'text', value: seg.value.slice(l) });
  }

  return expanded.map((seg, i) => {
    const key = `${keyPrefix}-i${i}`;
    if (seg.kind === 'bold') {
      return <strong key={key} className="text-slate-100">{wrapTerms(seg.value, wrapped, TermComponent, key)}</strong>;
    }
    if (seg.kind === 'italic') {
      return <em key={key}>{wrapTerms(seg.value, wrapped, TermComponent, key)}</em>;
    }
    return <span key={key}>{wrapTerms(seg.value, wrapped, TermComponent, key)}</span>;
  });
}

// Block parser: paragraphs, ##/### headings, --- horizontal rules, * / - lists.
function parseBlocks(text) {
  const lines = text.split('\n');
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();

    if (!line) { i++; continue; }

    if (/^([-*_])\1{2,}\s*$/.test(line)) {
      blocks.push({ kind: 'hr' });
      i++;
      continue;
    }

    const headingMatch = line.match(/^(#{1,3})\s+(.+?)\s*$/);
    if (headingMatch) {
      blocks.push({ kind: 'heading', level: headingMatch[1].length, text: headingMatch[2] });
      i++;
      continue;
    }

    if (/^[*\-+]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[*\-+]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[*\-+]\s+/, ''));
        i++;
      }
      blocks.push({ kind: 'list', items });
      continue;
    }

    // Paragraph: consume until blank line or block-starting line.
    const paraLines = [line];
    i++;
    while (i < lines.length) {
      const next = lines[i].trim();
      if (!next) break;
      if (/^(#{1,3})\s+/.test(next)) break;
      if (/^([-*_])\1{2,}\s*$/.test(next)) break;
      if (/^[*\-+]\s+/.test(next)) break;
      paraLines.push(next);
      i++;
    }
    blocks.push({ kind: 'paragraph', text: paraLines.join(' ') });
  }
  return blocks;
}

export function renderNarrative(text, TermComponent) {
  if (!text) return null;
  const blocks = parseBlocks(text);

  return blocks.map((block, bi) => {
    const wrapped = new Set();
    const keyPrefix = `b${bi}`;

    if (block.kind === 'hr') {
      return <hr key={keyPrefix} className="border-slate-800/60 my-4" />;
    }
    if (block.kind === 'heading') {
      const inner = renderInline(block.text, wrapped, TermComponent, keyPrefix);
      const cls = block.level === 1
        ? 'text-lg font-semibold text-slate-100 mt-4 mb-2'
        : block.level === 2
          ? 'text-base font-semibold text-slate-100 mt-4 mb-2'
          : 'text-sm font-semibold text-slate-200 mt-3 mb-1';
      return <div key={keyPrefix} className={cls}>{inner}</div>;
    }
    if (block.kind === 'list') {
      return (
        <ul key={keyPrefix} className="list-disc pl-5 space-y-1 my-3 marker:text-slate-500">
          {block.items.map((item, li) => (
            <li key={`${keyPrefix}-li${li}`}>
              {renderInline(item, wrapped, TermComponent, `${keyPrefix}-li${li}`)}
            </li>
          ))}
        </ul>
      );
    }
    return (
      <p key={keyPrefix} className="mb-3 last:mb-0">
        {renderInline(block.text, wrapped, TermComponent, keyPrefix)}
      </p>
    );
  });
}
