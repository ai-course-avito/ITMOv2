import inspect
import logfire
from functools import wraps

from .masking import mask_arguments, mask_value


def log_function_result(func, args, kwargs, result):
    line = f"Function {func.__name__} returned {result.__class__.__name__}"
    logfire.debug(
        line,
        arguments=mask_arguments(func, args, kwargs),
        result=mask_value(result, "result"),
    )


def async_logfire_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        log_function_result(func, args, kwargs, result)

        return result

    return wrapper


def decorate_methods(decorator):
    def result_decorator(cls):
        for method_name in dir(cls):
            if method_name.startswith("_"):
                continue

            method = getattr(cls, method_name)

            # Only coroutine functions: the wrapper awaits what it calls, so anything
            # else (e.g. `transaction()`, a context manager) must be left as it is.
            if inspect.iscoroutinefunction(method):
                setattr(cls, method_name, decorator(method))
        return cls

    return result_decorator


def async_logfire_class_decorator(cls):
    return decorate_methods(async_logfire_decorator)(cls)
