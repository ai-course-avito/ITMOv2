import ast
import operator

Number = int | float


class CalculatorError(ValueError):
    pass


def _divide(left: Number, right: Number) -> Number:
    if isinstance(left, int) and isinstance(right, int) and left % right == 0:
        return left // right
    return left / right


BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: _divide,
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _evaluate(node: ast.AST) -> Number:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in BINARY_OPERATORS:
        return BINARY_OPERATORS[type(node.op)](_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPERATORS:
        return UNARY_OPERATORS[type(node.op)](_evaluate(node.operand))
    raise CalculatorError("unsupported expression")


def calculate(expression: str) -> Number:
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError) as error:
        raise CalculatorError("invalid expression") from error
    try:
        return _evaluate(tree.body)
    except ZeroDivisionError as error:
        raise CalculatorError("division by zero") from error
    except OverflowError as error:
        raise CalculatorError("result is too large") from error
