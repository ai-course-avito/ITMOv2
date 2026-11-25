import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const workflow = JSON.parse(readFileSync(new URL('./autofix.json', import.meta.url)));
const path = 'practices/practice_07.2/autofix_demo/is-weekend.mjs';
const base = 'a'.repeat(40), fileSha = 'b'.repeat(40), head = 'c'.repeat(40);
const report = {
  action: 'labeled', label: { name: 'bug' }, sender: { login: 'bronY9' },
  repository: { full_name: 'bronY9/ITMOv2', default_branch: 'main' },
  issue: {
    title: '[autofix] Sunday is not recognized as a weekend', state: 'open',
    number: 30, author_association: 'OWNER', user: { login: 'bronY9' },
    body: 'isWeekend(0) should be true, and isWeekend(7) should be false.',
  },
};
const original = '// JavaScript getDay(): Sunday = 0, Saturday = 6.\nexport function isWeekend(day) {\n  return day === 6 || day === 7;\n}\n';
const outputs = new Map();
const first = json => ({ first: () => ({ json }) });
function run(name, input) {
  const node = workflow.nodes.find(n => n.name === name);
  const execute = new Function('$input', '$', 'Buffer', node.parameters.jsCode);
  const result = execute(first(input), name => first(outputs.get(name)), Buffer);
  if (result.length) outputs.set(name, result[0].json);
  return result;
}
for (const node of workflow.nodes.filter(n => n.type.endsWith('.code'))) {
  new Function(node.parameters.jsCode);
}
assert.deepEqual(run('Разрешённый учебный баг', { ...report, sender: { login: 'other' } }), []);
assert.deepEqual(run('Разрешённый учебный баг', { ...report, label: { name: 'task' } }), []);
assert.equal(run('Разрешённый учебный баг', report)[0].json.branch, 'practice072-autofix/issue-30');
outputs.set('SHA основной ветки', { object: { sha: base } });
run('Подготовить исходник', { path, sha: fileSha, type: 'file', encoding: 'base64', content: Buffer.from(original).toString('base64') });
assert.throws(() => run('Проверить правку и граничные дни', { text: 'return day === 6 || day === 7;' }));
assert.throws(() => run('Проверить правку и граничные дни', { text: 'return true;' }));
const proposed = run('Проверить правку и граничные дни', { text: 'return day === 0 || day === 6;' })[0].json;
assert.equal(proposed.tests.length, 13);
const { isWeekend } = await import('data:text/javascript;base64,' + proposed.encoded);
for (const t of proposed.tests) assert.equal(isWeekend(t.day), t.expected);

outputs.set('Записать исправление', { commit: { sha: head }, content: { sha: fileSha } });
outputs.set('Открыть Pull Request', {
  number: 31, base: { ref: 'main', sha: base },
  head: { ref: 'practice072-autofix/issue-30', sha: head },
});
const file = { filename: path, status: 'modified', sha: fileSha, additions: 1, deletions: 1,
  patch: '-  return day === 6 || day === 7;\n+  return day === 0 || day === 6;' };
const compare = { ahead_by: 1, behind_by: 0, commits: [{ sha: head }], files: [file] };
assert.throws(() => run('Сверить коммит и состав правки', { ...compare, files: [file, file] }));
assert.throws(() => run('Сверить коммит и состав правки', { ...compare, commits: [{ sha: base }] }));
run('Сверить коммит и состав правки', compare);
const review = { id: 2, state: 'COMMENTED', commit_id: head };
for (const text of ['BLOCK', 'APPROVE but needs work', '']) {
  run('Решение ревью', { text });
  assert.deepEqual(run('Разрешить слияние', review), []);
}
run('Решение ревью', { text: 'APPROVE' });
assert.throws(() => run('Разрешить слияние', { ...review, commit_id: base }));
assert.equal(run('Разрешить слияние', review)[0].json.sha, head);
assert.throws(() => run('Основная ветка не изменилась', { object: { sha: head } }));
assert.equal(run('Основная ветка не изменилась', { object: { sha: base } })[0].json.sha, head);
assert.throws(() => run('Подтвердить merge', { merged: false }));
console.log('OK: фильтр Issues, 13 проверок isWeekend, один файл и SHA, блокировка merge, контроль main.');

