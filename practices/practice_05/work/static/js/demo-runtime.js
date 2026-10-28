window.createDemoRuntime = function (calculate) {
  let revision = 0;
  let pending = null;
  return {
    run(state, onSuccess, onError) {
      const current = ++revision;
      if (pending && typeof pending.abort === 'function') pending.abort();
      pending = calculate(state);
      return Promise.resolve(pending).then((result) => {
        if (current === revision) onSuccess(result);
        return current === revision;
      }).catch((error) => {
        if (current === revision && onError) onError(error);
        return false;
      });
    },
    cancel() { revision += 1; if (pending && typeof pending.abort === 'function') pending.abort(); },
  };
};
