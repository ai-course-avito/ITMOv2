// B3: рекорд в Web Storage. Хранилище передаётся параметром, поэтому модуль
// не трогает DOM и проверяется в node с подменой хранилища.
// null вместо числа означает «хранилище недоступно — играем без рекорда».

const RECORD_KEY = "tetris.record";

// Само обращение к window.localStorage бросает SecurityError, если сайту
// запрещено хранить данные; тогда хранилища нет.
export function localStorageOf(win) {
  try {
    return win.localStorage ?? null;
  } catch {
    return null;
  }
}

// Рекорд — неотрицательное целое; всё остальное в хранилище считается мусором.
export function readRecord(storage) {
  try {
    const value = Number(storage.getItem(RECORD_KEY));
    return Number.isSafeInteger(value) && value > 0 ? value : 0;
  } catch {
    return null;
  }
}

// Записывает счёт, только если он выше рекорда; возвращает действующий рекорд.
// Если записать новый рекорд не удалось, действующим остаётся прочитанный.
// null — только когда хранилища нет или из него нельзя читать.
export function saveRecord(storage, score) {
  const current = readRecord(storage);
  if (current === null || score <= current) return current;
  try {
    storage.setItem(RECORD_KEY, String(score));
    return score;
  } catch {
    return current;
  }
}
