import test from "node:test";
import assert from "node:assert/strict";

import {
  add,
  subtract,
  multiply,
  divide
} from "../src/calculator.js";

test("add складывает два числа", () => {
  assert.equal(add(2, 3), 5);
});

test("subtract вычитает второе число из первого", () => {
  assert.equal(subtract(5, 3), 2);
});

test("multiply умножает два числа", () => {
  assert.equal(multiply(4, 5), 20);
});

test("multiply работает с отрицательным числом", () => {
  assert.equal(multiply(-3, 4), -12);
});

test("divide делит первое число на второе", () => {
  assert.equal(divide(10, 2), 5);
});

test("divide работает с дробным результатом", () => {
  assert.equal(divide(5, 2), 2.5);
});

test("divide запрещает деление на ноль", () => {
  assert.throws(
    () => divide(10, 0),
    /Division by zero/
  );
});