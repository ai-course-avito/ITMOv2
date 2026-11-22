// Фича B3 — рекорд в localStorage. Хранилище подменяется объектом с тем же
// интерфейсом, что у Web Storage: getItem → строка или null, setItem пишет строку.
import test from "node:test";
import assert from "node:assert/strict";
import { readRecord, saveRecord, localStorageOf } from "../src/record.js";

class MemoryStorage {
  #items = new Map();
  get length() {
    return this.#items.size;
  }
  key(index) {
    return [...this.#items.keys()][index] ?? null;
  }
  getItem(key) {
    return this.#items.has(key) ? this.#items.get(key) : null;
  }
  setItem(key, value) {
    this.#items.set(key, String(value));
  }
  removeItem(key) {
    this.#items.delete(key);
  }
  clear() {
    this.#items.clear();
  }
}

test("B3: в пустом хранилище рекорд равен 0", () => {
  assert.equal(readRecord(new MemoryStorage()), 0);
});

test("B3: счёт выше рекорда сохраняется и читается как новый рекорд", () => {
  const storage = new MemoryStorage();
  assert.equal(saveRecord(storage, 1240), 1240);
  assert.equal(readRecord(storage), 1240);
});

test("B3: счёт ниже рекорда рекорд не меняет", () => {
  const storage = new MemoryStorage();
  storage.setItem("tetris.record", "800");
  assert.equal(saveRecord(storage, 300), 800);
  assert.equal(readRecord(storage), 800);
});

test("B3: испорченное значение в хранилище читается как 0", () => {
  for (const raw of ["abc", "", "-5", "Infinity", "12.5"]) {
    const storage = new MemoryStorage();
    storage.setItem("tetris.record", raw);
    assert.equal(readRecord(storage), 0, JSON.stringify(raw));
  }
});

// ---------- хранилище недоступно: игра работает без рекорда (null) ----------

// Хранилище, где все обращения бросают ошибку, как в браузере с запретом cookies.
class BlockedStorage extends MemoryStorage {
  getItem() {
    throw new DOMException("The operation is insecure.", "SecurityError");
  }
  setItem() {
    throw new DOMException("The operation is insecure.", "SecurityError");
  }
}

// Чтение работает, запись бросает ошибку, как при переполненной квоте.
// saved — значение, записанное в хранилище до того, как оно переполнилось.
class FullStorage extends MemoryStorage {
  constructor(saved) {
    super();
    if (saved !== undefined) super.setItem("tetris.record", saved);
  }
  setItem() {
    throw new DOMException("Quota exceeded.", "QuotaExceededError");
  }
}

test("B3: без хранилища рекорда нет", () => {
  assert.equal(readRecord(null), null);
  assert.equal(saveRecord(null, 500), null);
});

test("B3: если чтение из хранилища бросает ошибку, рекорда нет", () => {
  assert.equal(readRecord(new BlockedStorage()), null);
});

test("B3: если и чтение, и запись бросают ошибку, saveRecord не падает и рекорда нет", () => {
  assert.equal(saveRecord(new BlockedStorage(), 500), null);
});

test("B3: счёт не выше рекорда в хранилище без записи оставляет прежний рекорд", () => {
  // Писать нечего, поэтому сбой записи не должен прятать рекорд 800.
  assert.equal(saveRecord(new FullStorage("800"), 300), 800);
  assert.equal(saveRecord(new FullStorage("800"), 800), 800);
});

test("B3: если запись нового рекорда упала, остаётся прежний прочитанный рекорд", () => {
  assert.equal(saveRecord(new FullStorage("800"), 1000), 800);
  assert.equal(saveRecord(new FullStorage(), 500), 0);
});

test("B3: если обращение к window.localStorage бросает ошибку, хранилища нет", () => {
  const win = {
    get localStorage() {
      throw new DOMException("Access is denied for this document.", "SecurityError");
    },
  };
  assert.equal(localStorageOf(win), null);
});

test("B3: доступное window.localStorage возвращается как есть", () => {
  const storage = new MemoryStorage();
  assert.equal(localStorageOf({ localStorage: storage }), storage);
});
