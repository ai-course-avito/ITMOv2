window.MathJax = { tex: { inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] }, options: { skipHtmlTags: ['noscript', 'style', 'textarea', 'pre', 'code'] } };
window.typesetMath = function (nodes) {
  if (!window.MathJax?.typesetPromise) return Promise.resolve();
  return window.MathJax.typesetPromise(nodes || undefined);
};
