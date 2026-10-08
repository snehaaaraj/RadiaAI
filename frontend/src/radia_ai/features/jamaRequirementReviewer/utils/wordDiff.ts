export type DiffPart = { type: 'same' | 'added' | 'removed'; text: string };

/**
 * Word-level diff between two texts (longest common subsequence over words).
 *
 * Used only to highlight what changed between the original and the recommended
 * Description; the recommendation itself is produced by the backend.
 */
export function diffWords(original: string, revised: string): DiffPart[] {
  const a = tokenize(original);
  const b = tokenize(revised);

  const lcs: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }

  const parts: DiffPart[] = [];
  const push = (type: DiffPart['type'], word: string) => {
    const last = parts[parts.length - 1];
    if (last && last.type === type) {
      last.text += ` ${word}`;
    } else {
      parts.push({ type, text: word });
    }
  };

  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      push('same', a[i]);
      i += 1;
      j += 1;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      push('removed', a[i]);
      i += 1;
    } else {
      push('added', b[j]);
      j += 1;
    }
  }
  for (; i < a.length; i += 1) push('removed', a[i]);
  for (; j < b.length; j += 1) push('added', b[j]);
  return parts;
}

function tokenize(text: string): string[] {
  return text.split(/\s+/).filter(Boolean);
}
